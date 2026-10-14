# Despliegue en la máquina de Azure (2026-10-14)

Procedimiento real, con los comandos que se usaron de verdad, para montar la
plataforma en `adif-catalogo-ineco.spaincentral.cloudapp.azure.com`
(158.158.50.88, Ubuntu 24.04, usuario `adif`). Todo se ejecutó desde el
portátil de desarrollo (Windows 11, Git Bash) por SSH. La referencia general
es [guia-de-operacion.md](guia-de-operacion.md); aquí queda lo que se hizo y
lo que hubo que cambiar.

## Bloque 1. Acceso por SSH

La clave original de la máquina se generó en Cloud Shell y se perdió. Se creó
una clave propia para esta máquina en el portátil:

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519_adif -N '""' -C "adif-vm" -q
```

Huella: `SHA256:Oa1e+uShKV0uPfB4HlzU7s+3s50yvCIcTETQklUXT6M`. Se registró
desde Cloud Shell:

```bash
az vm user update -g <grupo> -n <vm> --username adif \
  --ssh-key-value "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP+2E4/m6sGEZOhotvgve6t4/fT8sOUvmrCdYjkTTGZh adif-vm"
```

Para no indicar la clave en cada comando (`ssh`, `scp`, `rsync`), en
`%USERPROFILE%\.ssh\config` del portátil:

```
Host adif-catalogo-ineco.spaincentral.cloudapp.azure.com 158.158.50.88
    User adif
    IdentityFile ~/.ssh/id_ed25519_adif
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 6
```

Lo leen igual el `ssh` de Windows y el de Git Bash (`ssh -G <host>` lo
confirma). Comprobación de entrada y de `sudo` sin contraseña:

```bash
ssh -o BatchMode=yes adif-catalogo-ineco.spaincentral.cloudapp.azure.com 'whoami; sudo -n true && echo SUDO OK'
```

En `~/.ssh/authorized_keys` de `adif` había tres claves: la RSA original de
Cloud Shell (perdida), una de otro proyecto registrada por error y la nueva.
Se dejó solo la nueva, comprobando antes que estaba y sustituyendo el fichero
de una vez:

```bash
cd ~/.ssh
grep -F "AAAAC3NzaC1lZDI1NTE5AAAAIP+2E4/m6sGEZOhotvgve6t4/fT8sOUvmrCdYjkTTGZh adif-vm" authorized_keys > ak.nuevo
[ "$(wc -l < ak.nuevo)" = 1 ] && chmod 600 ak.nuevo && mv ak.nuevo authorized_keys
```

Después se volvió a entrar con la clave nueva (bien) y se probó la del otro
proyecto (`Permission denied (publickey)`).
