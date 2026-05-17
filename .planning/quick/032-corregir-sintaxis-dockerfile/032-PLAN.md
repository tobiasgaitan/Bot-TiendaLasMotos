---
task: 032
name: Corregir Sintaxis de Dockerfile
description: La compilación en Google Cloud Build ha fallado en la construcción de la imagen debido a colisiones de espaciado en las directivas de copia COPY. Se requiere corregir quirúrgicamente el archivo Dockerfile para restaurar el espaciado adecuado.
---

# Quick Task 032: Corregir Sintaxis de Dockerfile

## Objective
Corregir los errores de espaciado en las directivas `COPY` del archivo `Dockerfile` para resolver el fallo de construcción de imagen en Google Cloud Build y verificar localmente la pre-compilación usando `docker build`.

## Tasks

<task type="auto">
  <name>Corregir sintaxis de COPY en Dockerfile</name>
  <files>Dockerfile</files>
  <action>Editar quirúrgicamente las líneas de COPY en Dockerfile para añadir los espacios correspondientes: restaurar 'README.md ./' y 'COPY ./app ./app'. Validar que 'git' continúe en las dependencias de apt-get.</action>
  <verify>docker build -t bot-tiendalasmotos:test .</verify>
  <done>El archivo Dockerfile ha sido modificado y la imagen de Docker se compila localmente de forma exitosa sin errores sintácticos en las instrucciones COPY.</done>
</task>

---
*Created: 2026-05-17*
