# Guía de operación

Para quien administra la máquina de producción. Todo se hace por SSH, como
`sudo`, desde la carpeta `deploy/` del repositorio:

```bash
cd /opt/adif/deploy
alias adif='sudo docker compose -f docker-compose.prod.yml'
```

Los comandos de abajo usan ese alias.

## Qué hay

| Contenedor | Qué hace | Puertos al exterior |
|---|---|---|
| `entrada` | Caddy: HTTPS con certificado automático, redirige el 80 al 443, sirve la web en `/` y la API en `/api` | 80, 443 |
| `web` | Next.js | ninguno |
| `api` | FastAPI, única puerta a los datos | ninguno |
| `worker` | Descargas, extracción, mantenimiento semanal, copias de la base | ninguno |
| `postgres` | Base de datos | ninguno |

| En la máquina | Qué es |
|---|---|
| `/opt/adif` | El repositorio. El código que corre sale de aquí |
| `/opt/adif/deploy/.env` | La configuración, con las claves (permisos 600). No se sube a ningún sitio |
| `/srv/adif/documentos` | Los PDF descargados |
| `/srv/adif/copias` | Copias diarias de la base |
| `/srv/adif/entrada` | Ficheros de entrada del cliente (Excel de SAP, maestro...) |
| `/srv/adif/traspaso` | Donde se dejan los datos traídos de otra máquina |

## Instalar desde cero

1. **En Azure**, en el grupo de seguridad de red de la máquina, abrir los
   puertos 443 y 80 (TCP). El 80 hace falta para que la redirección a HTTPS
   llegue a funcionar; el certificado se puede obtener solo con el 443. Y el
   22 para SSH, a ser posible limitado a las direcciones de quien administra.
2. **En la máquina de origen** (hoy, el portátil con WSL), dentro de WSL:

   ```bash
   cd /mnt/c/dev/ADIF && mkdir -p traspaso
   # Base de datos, con el pg_dump del propio contenedor de PostgreSQL 16
   docker exec adif-postgres-1 pg_dump -U adif -d adif -Fc -f /tmp/adif.dump
   docker cp adif-postgres-1:/tmp/adif.dump traspaso/adif.dump
   docker exec adif-postgres-1 rm /tmp/adif.dump
   # Documentos descargados
   docker exec adif-api-1 tar -cf - -C /data/documentos . > traspaso/documentos.tar
   ```

   Ocupan unos 45 MB y 1,9 GB (medido el 14/10/2026).
3. **En la máquina nueva**:

   ```bash
   sudo git clone <repositorio> /opt/adif
   sudo mkdir -p /srv/adif/traspaso && sudo chown $USER /srv/adif/traspaso
   ```

4. **De vuelta en la máquina de origen**, subir los dos ficheros:

   ```bash
   scp traspaso/adif.dump traspaso/documentos.tar <usuario>@adif-catalogo-ineco.spaincentral.cloudapp.azure.com:/srv/adif/traspaso/
   ```

5. **En la máquina nueva**, instalar:

   ```bash
   sudo /opt/adif/deploy/instalar.sh
   ```

   Instala Docker, crea `/srv/adif`, crea `deploy/.env` con una contraseña de
   base generada al azar, construye, levanta, restaura los datos de
   `traspaso/` y deja el arranque automático puesto. La primera vez tarda unos
   10 minutos. Al terminar, `https://adif-catalogo-ineco.spaincentral.cloudapp.azure.com`
   enseña la pantalla de entrada.
6. Crear los usuarios (abajo) y, si se va a usar, configurar el modelo de IA.
7. Borrar `/srv/adif/traspaso/*` cuando todo esté comprobado.

Si `instalar.sh` se ejecuta sin datos en `traspaso/`, deja todo levantado
salvo el worker: con la base vacía, su primer ciclo de mantenimiento se
pondría a descargar la Plataforma entera. Para restaurar después:
`sudo ./restaurar-datos.sh`.

## Usuarios

Un solo perfil: consulta, revisa y exporta. No hay administración desde la web.

```bash
adif exec api python -m app.usuarios crear ana.garcia      # imprime una contraseña temporal
adif exec api python -m app.usuarios reiniciar ana.garcia  # contraseña temporal nueva
adif exec api python -m app.usuarios desactivar ana.garcia # no puede entrar; cierra sus sesiones
adif exec api python -m app.usuarios activar ana.garcia
adif exec api python -m app.usuarios listar                # usuarios y su última entrada
adif exec api python -m app.usuarios accesos               # entradas, salidas y fallos
adif exec api python -m app.usuarios accesos --usuario ana.garcia --limite 100
```

- La contraseña temporal se entrega por un canal aparte. En la primera
  entrada la web obliga a cambiarla (mínimo 12 caracteres).
- La sesión se cierra tras 30 minutos sin actividad y, en todo caso, a las
  12 horas.
- 5 fallos seguidos de un usuario (o 20 desde una misma dirección) en 15
  minutos lo bloquean durante esos 15 minutos, incluso con la contraseña
  correcta. No hay que hacer nada: se desbloquea solo.

Los valores están en `deploy/.env` (`SESION_*`, `ACCESO_*`).

## Modelo de IA

Solo hace falta para leer documentos escaneados nuevos y tablas con una
cabecera nunca vista. Sin clave, consultar, revisar y exportar funciona igual,
lo ya leído sigue en caché, y la pantalla de Mantenimiento lo avisa.

Para usar el servicio de IA del cliente, en `deploy/.env`:

```
MODEL_PROVEEDOR=openai
MODEL_ENDPOINT=https://<recurso>.openai.azure.com/openai/v1
MODEL_ID=<nombre del despliegue; con visión si se van a leer escaneados>
MODEL_API_KEY=<clave>
```

y aplicar con `adif up -d api worker`. Cambiar de modelo o de proveedor no
vuelve a leer nada de lo ya leído. La pantalla de Mantenimiento enseña el
proveedor y el modelo en uso; el registro del worker
(`adif logs worker | grep "modelo de IA"`) también.

## Día a día

```bash
adif ps                       # estado de los cinco contenedores
adif logs --tail 100 worker   # registro de uno
adif restart api              # reiniciar uno
```

**Actualizar a una versión nueva del código**:

```bash
cd /opt/adif && sudo git pull && sudo deploy/instalar.sh
```

Reconstruye y levanta; la API aplica sola las migraciones de la base al
arrancar. **Si el `git pull` cambia `deploy/Caddyfile`**, además
`adif restart entrada`: el fichero está montado suelto en el contenedor, y
`git` lo sustituye por otro, que Caddy no ve hasta reiniciarse (`instalar.sh`
no lo reinicia si nada más ha cambiado).

**Exportar el Excel** tarda unos 4 minutos (234 s medido el 14/10/2026, con
19.351 filas) y el navegador no recibe nada hasta el final. Dos usuarios a la
vez tardan unos 5 minutos y medio cada uno (327 s): la API es un solo proceso
y se reparten el procesador, sin estorbarse más que eso. Caddy corta a los 10
minutos (`deploy/Caddyfile`); con cuatro o más exportaciones a la vez se
llegaría a ese límite. Firefox, por su cuenta, deja de esperar una respuesta a
los 5 minutos (`network.http.response.timeout`): con dos exportaciones a la
vez, mejor Chrome o Edge.

**Reinicio de la máquina**: todo vuelve a arrancar solo (servicio
`adif.service` de systemd, más `restart: unless-stopped` en cada
contenedor). Comprobar con `adif ps`.

## Copias de seguridad

El worker hace una copia completa de la base cada 24 horas en
`/srv/adif/copias/adif_AAAAMMDD_HHMMSS.dump` (unos 45 MB) y guarda las 14
últimas; las más antiguas las borra él. Ajustable en `deploy/.env`
(`BACKUP_INTERVALO_SEGUNDOS`, `BACKUP_RETENCION`). La web no tiene botón
para forzar una; se fuerza con la API, desde el navegador con una sesión
abierta (consola de las herramientas de desarrollo):
`fetch('/api/mantenimiento/copias/ejecutar', {method: 'POST', credentials: 'include'})`.
La siguiente automática pasa a ser 24 horas después de esa.

Las copias están en el mismo disco que la base: protegen de un error, no de
perder la máquina. Conviene llevarse una de vez en cuando fuera
(`scp` de la más reciente) o activar la copia de la máquina en Azure.

Los documentos no entran en la copia diaria. Se pueden volver a descargar de
la Plataforma, pero tarda: guardar de vez en cuando
`sudo tar -cf documentos.tar -C /srv/adif/documentos .`.

**Restaurar una copia automática** (sustituye la base entera):

```bash
adif stop entrada web worker api
adif run --rm --no-deps worker sh -c \
  'PGPASSWORD=$POSTGRES_PASSWORD pg_restore -h postgres -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists --no-owner /backups/adif_AAAAMMDD_HHMMSS.dump'
adif up -d
```

Se restaura con el `pg_restore` del motor, no con el del contenedor de
PostgreSQL: las copias automáticas las hace un `pg_dump` 17 y el servidor es
16, que no sabe leerlas.

## Si algo falla

- **La web no carga y el navegador habla del certificado**: Caddy no ha
  podido obtenerlo. `adif logs entrada`. Lo normal es que el 443 no esté
  abierto en Azure o que el dominio no apunte a la máquina.
- **La API no arranca**: `adif logs api`. Si es la base, `adif logs postgres`.
- **Un expediente en revisión con "no hay modelo de IA configurado"**: es un
  escaneado nuevo y falta `MODEL_API_KEY`. Con la clave puesta, volver a
  lanzar la extracción del expediente desde la web.
- **Disco**: `df -h /` y `sudo du -sh /srv/adif/*`. Los registros de Docker
  están acotados a 100 MB por contenedor.
