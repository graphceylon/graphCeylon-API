FROM nginx:1.27-alpine

RUN apk add --no-cache certbot certbot-nginx

COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
