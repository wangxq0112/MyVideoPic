"""
Django settings for MyVideoPic — 纯本地极简媒体中心.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# 纯本地应用，密钥不参与任何对外通信；仍支持用环境变量覆盖
SECRET_KEY = os.environ.get(
    'MYVIDEOPIC_SECRET_KEY',
    'django-insecure-local-only-myvideopic-2026-do-not-expose',
)

DEBUG = _bool_env('MYVIDEOPIC_DEBUG', True)

# 只监听本机名 —— 不接受来自局域网其他主机的 Host 头
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    # Local
    'videos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# SQLite — 零配置单文件数据库
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 单用户本地应用：上传体积无限制（仅影响 multipart 解析，本项目不用）
DATA_UPLOAD_MAX_MEMORY_SIZE = None

# ── DRF ──────────────────────────────────────────────
# 单用户离线应用：不做鉴权，也不启用 SessionAuthentication
# （后者会对写接口强制 CSRF token，而本应用没有登录态）。
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'videos.pagination.StandardPagination',
    'PAGE_SIZE': 50,
    'UNAUTHENTICATED_USER': None,
}

# ── 应用数据目录（缩略图缓存）────────────────────────
# 所有生成物只落在这里，原始媒体文件夹全程只读、绝不写入任何隐藏文件
APP_DATA_DIR = Path(os.environ.get('MYVIDEOPIC_APP_DATA', BASE_DIR / '.app_data'))
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

THUMBNAIL_SIZE = (480, 360)

# ── Nginx 零拷贝出流 ─────────────────────────────────
# 关闭时由 Django 自行处理 206 Range（开发默认）
# 开启时改回 X-Accel-Redirect，由 Nginx sendfile 直接发送字节
USE_X_ACCEL = _bool_env('MYVIDEOPIC_X_ACCEL', False)
X_ACCEL_PREFIX = '/_protected'

# ── 跨域 ─────────────────────────────────────────────
# 不需要任何 CORS 配置：开发期 Vite 把 /api 代理到 Django，
# 部署期 Nginx 反代 /api，两种情况下前端都是同源请求。

# ── 日志：后台线程里的异常要能在控制台看到 ───────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}
