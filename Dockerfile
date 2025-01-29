FROM python:3.9

WORKDIR /app

COPY init.sh /init.sh
RUN chmod +x /init.sh

RUN pip install --no-cache-dir -r <(python3 -m pip freeze) \
    --target /app/lyrics  \
    --target /app/music  \
    --target /app/config
   

ENV MUSICBRAINZ_USERAGENT="default_user"
ENV MUSICBRAINZ_VERSION="1.0"
ENV MUSICBRAINZ_CONTACT="default@example.com"
ENV BOT_OWNER_ID=123456789
ENV EXECUTOR_MAX_WORKERS=10
ENV BOT_TOKEN="your_default_token"


CMD ["/init.sh"] 

