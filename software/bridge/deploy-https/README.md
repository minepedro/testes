# HTTPS por IP para a ponte do mascote

Let's Encrypt emite certificado para IP (`179.198.122.200`) só com o perfil `shortlived` (6 dias).
É preciso certbot >= 5.4 para `--webroot` com `--ip-address`
(<https://letsencrypt.org/2026/03/11/shorter-certs-certbot>). O plugin nginx do certbot
não instala esse cert, então o nginx é configurado por este script e um deploy-hook recarrega
o nginx a cada renovação.

## O que é instalado
| Item | Caminho | Modo |
|---|---|---|
| nginx (apt), site preso só a `179.198.122.200:80/443` | `/etc/nginx/sites-available/mascote-https.conf` | 0644 |
| include do proxy | `/etc/nginx/mascote-proxy.inc` | 0644 |
| certbot isolado (venv) | `/opt/certbot-venv` | 0755 |
| webroot ACME | `/var/www/mascote-acme` | 0755 |
| deploy hook (valida o cert, roda `nginx -t` e depois reload) | `/etc/letsencrypt/renewal-hooks/deploy/mascote-nginx-reload.sh` | 0755 |
| timer de renovação (a cada 6 h) | `/etc/systemd/system/mascote-certbot.{service,timer}` | 0644 |
| drop-in da ponte em loopback (só no activate) | `/etc/systemd/system/mascote-ponte.service.d/10-loopback.conf` | 0644 |
| token novo (só no activate) | `/etc/mascote-ponte.env` | 0600 root |
| backups e log | `/var/lib/mascote-https/backups` (0700), `/var/log/mascote-https.log` (0600) | |

O nginx não escuta em `0.0.0.0` nem em `[::]`, então o Tailscale (`100.94.88.50:443` e
`fd7a:…:443`) não é afetado. O SSH, o reboot e outros serviços não são tocados. O site
`default` do nginx é desabilitado e fica guardado em backup; `rollback-prepare` **não** o reabilita
(reexporia `0.0.0.0:80`). Para reativar, faça à mão e conscientemente.

## Comandos
Os modos `render`, `preflight`, `verify` e os testes não precisam de root.
```sh
cd software/bridge/deploy-https
python3 mascote_https.py render --out /tmp/mascote-render   # revise os arquivos gerados
python3 mascote_https.py preflight                           # IP, portas 80/443, upstream /saude=200 e /api/estado=401
```
**Fase 1, prepare.** O ESP antigo continua funcionando: a ponte segue em `0.0.0.0:8787` com o token antigo.
```sh
sudo python3 mascote_https.py prepare --staging-only   # opcional: só testa contra o staging (dry-run)
sudo python3 mascote_https.py prepare                  # dry-run no staging -> cert de produção -> nginx TLS -> timer -> renew --dry-run -> verify
python3 mascote_https.py verify                        # curl sem -k: /saude 200, /api/estado 401, /nada 404
```
**Fase 2, activate.** Rode só quando o firmware HTTPS estiver pronto para o flash.
```sh
sudo python3 mascote_https.py activate      # pede para digitar ATIVAR; gera token novo, ponte em 127.0.0.1, remove a regra UFW 8787
python3 mascote_https.py verify --require-closed
```
Escopo: só a instalação demo existente com `/etc/mascote-ponte.env` (root, 0600). `preflight` e
`activate` recusam se ele faltar (só `stat`, sem ler segredos); env ausente não é suportado.
O drop-in declara `EnvironmentFile=/etc/mascote-ponte.env` explicitamente (sem `-`: se sumir, a
unit falha em vez de subir sem token).

`activate` é transacional, nesta ordem: (1) verifica HTTPS público sem token antes de tocar no
env; (2) na **primeira** ativação grava snapshot imutável em `/var/lib/mascote-https/original`
(0700/0600: env + drop-in ou marca `.absent`); (3) token novo + drop-in + restart; (4) checa bind
só em `127.0.0.1` e auth (401/401/200) direto no upstream **antes** do UFW; (5) remove a regra
8787; (6) verify final. Falha em (3)/(4) restaura o snapshot sem tocar o UFW; falha em (6)
restaura e reabre 8787. Já ativado = recusa; para gerar outro token: `rollback-activate` e
`activate` (não há `--rotate-again`).

O token aparece uma única vez, e só se a saída for um terminal. Ele não vai para o log nem para
o argv: o curl recebe o token pelo stdin. Para ler depois: `sudo grep ^PONTE_TOKEN= /etc/mascote-ponte.env`.

**Rollback**
```sh
sudo python3 mascote_https.py rollback-activate   # env/drop-in do snapshot ORIGINAL (1a ativação), UFW 8787 aberto de novo
sudo python3 mascote_https.py rollback-prepare    # remove site/timer/hook e as regras UFW 80/443; mantém o cert, o nginx e o venv
```
Todos os modos podem ser rodados de novo com segurança. Arquivos iguais não são reescritos, e todo
arquivo alterado ganha backup com timestamp.

## Testes
```sh
python3 -m unittest discover -s tests -v
# com nginx real sem instalar (sem root):
apt-get download nginx && dpkg -x nginx_*.deb /tmp/ngx
NGINX_BIN=/tmp/ngx/usr/sbin/nginx python3 -W error::ResourceWarning -m unittest discover -s tests -v
```
O teste de integração sobe o `ponte.py` real em loopback e um nginx real com a config gerada
(apontada para `127.0.0.1` e portas altas), usando uma CA local. Ele verifica `/saude` 200,
401 sem token, 401 com token errado, 200 com token, 404, o desafio ACME por HTTP, o redirect 301
e a validação do cert pelo deploy-hook. A cadeia é validada com `--cacert`, e há um teste que
confirma que o curl **recusa** a conexão sem a CA. Sem nginx, esses testes são pulados.
A linha SAN do deploy-hook (`openssl x509 -checkip`, comparação literal da saída, pois o openssl
sai 0 mesmo sem match) roda contra certs reais: IP exato passa, `10.1.2.30` vs `10.1.2.3` falha.
`Lifecycle` cobre activate/rollback/prepare com os efeitos de root mockados (`run`, `chown`,
`verify`, `verify_local`) e arquivos em diretório temporário: ordem, rollback automático,
snapshot imutável 0600, recusa sem env, `policy-rc.d` e default do nginx.

## Riscos
- O cert vale 6 dias. Se a renovação falhar por mais de cerca de 3 dias, o ESP para de conectar.
  Acompanhe com `systemctl list-timers mascote-certbot.timer` e `journalctl -u mascote-certbot`.
- As portas 80 e 443 ficam abertas no UFW, mas só para o IP público. O provedor ou firewall
  externo também precisa liberar a porta 80 para o ACME.
- O ESP precisa confiar na raiz ISRG (ISRG Root X1/X2). Não use fingerprint do cert folha, porque
  ele muda a cada renovação.
- `activate` invalida o token antigo e fecha a porta 8787. Um ESP com o firmware antigo fica
  offline até receber o flash novo.
- `prepare` roda `apt-get update` e instala `nginx` e `python3-venv`. A instalação usa um
  `policy-rc.d` temporário para o site default não subir em `0.0.0.0:80`. Se já existir um
  `/usr/sbin/policy-rc.d` do administrador, `prepare` aborta antes do apt (não o sobrescreve).
- O timer renova só `--cert-name 179.198.122.200`; outros certs do certbot não são tocados.
- Não testado como root aqui (sem sudo). Os modos privilegiados (apt, certbot de verdade, UFW,
  systemctl) e um cert Let's Encrypt real por IP não foram executados; os testes de lifecycle
  usam mocks para esses efeitos.
