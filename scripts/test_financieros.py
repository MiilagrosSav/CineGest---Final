import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trabajofinal.settings')
import django
django.setup()

from datetime import timedelta
from django.utils import timezone
from reportes.selectors import get_datos_financieros

end = timezone.now()
start = end - timedelta(days=30)
res = get_datos_financieros(start, end, limit=5)
import json
print(json.dumps(res, indent=2, ensure_ascii=False))
