FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* se inserta en el bundle del navegador durante `next build`,
# no se puede pasar como variable de entorno en tiempo de ejecución —
# CONTEXTO.md sección 13: "la dirección de la API en la web es una variable de
# entorno", aquí en forma de build arg del propio contenedor.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
