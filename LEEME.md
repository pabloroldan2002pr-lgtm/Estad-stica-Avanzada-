# Estadística Avanzada 2ª FEB · web

Web con la estadística avanzada de la Segunda FEB (Grupos A y B, Copa España del Grupo A).
Se aloja gratis en GitHub Pages. Los datos se actualizan cuando pulsas **Actualizar datos** en la propia web.

## Qué hay en esta carpeta

| Archivo | Para qué sirve |
|---|---|
| `index.html` | La web (se regenera en cada actualización). |
| `data.json` | Todos los datos: partidos de liga, copa, calendario, escudos. |
| `plantilla.html` | Diseño de la web; el proceso le mete los datos y genera `index.html`. |
| `actualizar.py` | Lee BueStats, las actas de la FEB y la Copa España, y genera `data.json` e `index.html`. |
| `.github/workflows/actualizar.yml` | El proceso automático de GitHub que ejecuta `actualizar.py` y publica la web. |

## Puesta en marcha (una sola vez, unos 15 minutos)

1. **Crea una cuenta en GitHub** (gratis) en https://github.com/signup.
2. **Crea un repositorio**: botón **New** → nombre, por ejemplo, `estadistica-2feb` → **Public** → **Create repository**.
   (GitHub Pages gratis necesita que el repositorio sea público. Los datos son públicos de todas formas.)
3. **Sube los archivos**: en el repositorio, **Add file → Upload files** y arrastra `index.html`, `data.json`,
   `plantilla.html`, `actualizar.py` y `LEEME.md`. Pulsa **Commit changes**.
4. **Crea el proceso automático** (la carpeta `.github` suele estar oculta y no se puede arrastrar):
   **Add file → Create new file**, escribe como nombre `.github/workflows/actualizar.yml`,
   pega el contenido del archivo `actualizar.yml` que va suelto en esta carpeta (es una copia visible del de `.github/workflows`) y pulsa **Commit changes**.
5. **Activa la web**: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
6. **Primera actualización**: pestaña **Actions** → **Actualizar datos** → **Run workflow** → **Run workflow**.
   En unos 3 minutos la web estará en `https://TU-USUARIO.github.io/estadistica-2feb/`.

## Clave para que funcione el botón de la web

El botón **Actualizar datos** le pide a GitHub que ejecute el proceso. Para eso necesita una clave tuya,
que se guarda solo en el navegador donde la pegues (nunca en la web ni en el repositorio).

1. En GitHub: tu foto (arriba a la derecha) → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**.
2. **Token name**: `Actualizar estadística`. **Expiration**: la que quieras (máximo 1 año).
3. **Repository access → Only select repositories** → elige `estadistica-2feb`.
4. **Permissions → Repository permissions → Actions: Read and write**. Nada más.
5. **Generate token** y copia la clave (empieza por `github_pat_`).
6. En la web pulsa **Actualizar datos**: la primera vez aparece una casilla; pega la clave y pulsa
   **Guardar y actualizar**. En ese dispositivo ya no te la volverá a pedir.

Sin clave también puedes actualizar desde GitHub: **Actions → Actualizar datos → Run workflow**.

## Cómo funciona la actualización

1. Lee de BueStats el calendario de los dos grupos y los totales de cada partido jugado.
2. Para cada partido ya jugado que BueStats no tenga, busca el acta oficial en la FEB.
3. Lee la Copa España en la FEB y guarda los partidos jugados de los equipos del Grupo A.
4. Genera `data.json` e `index.html`, los guarda en el repositorio y publica la web.

Si BueStats o la FEB no responden, se mantienen los datos anteriores de esa fuente y el registro
de la ejecución (pestaña **Actions**) lo indica con un **AVISO**.

## Cambio de temporada

En `actualizar.py`, al principio: `TEMPORADA`, `BUESTATS_LIGAS` (ids de los grupos en BueStats)
y `COPA_URL` (dirección de resultados de la Copa España de esa temporada).
