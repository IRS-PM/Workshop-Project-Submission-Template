FROM node:22-alpine

WORKDIR /app
COPY remy/app/ ./

# The frontend is optional until its package manifest is added.
RUN if [ -f package-lock.json ]; then npm ci; \
    elif [ -f package.json ]; then npm install; \
    fi

EXPOSE 5173
CMD ["sh", "-c", "if [ -f package.json ]; then npm run dev -- --host 0.0.0.0; else echo 'Add remy/app/package.json to start the frontend'; sleep infinity; fi"]
