FROM makeplane/plane-backend:v1.5.0

COPY xiaohe_sso.py /code/plane/authentication/views/xiaohe_sso.py
COPY urls_xiaohe.py /code/plane/authentication/urls_xiaohe.py
COPY patch_urls.py /tmp/patch_urls.py

RUN python /tmp/patch_urls.py && rm -f /tmp/patch_urls.py
