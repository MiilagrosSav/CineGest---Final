from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, date, time, timedelta
from faker import Faker
import random

from django.db import transaction

from cine.models import pelicula as pelicula_module
from cine.models.pelicula import Pelicula
from cine.models.genero import Genero
from cine.models.sala import Sala
from cine.models.butaca import Butaca
from cine.models.funcion import Funcion

from accounts.models import Usuario, Cliente
from ventas.models import Venta, Entrada


class Command(BaseCommand):
    help = 'Pobla la base de datos con datos de prueba realistas para el módulo de Promociones.'

    def add_arguments(self, parser):
        parser.add_argument('--purge', action='store_true', help='Eliminar datos previamente generados por este script (emails con @faker.test) antes de poblar')

    def handle(self, *args, **options):
        fake = Faker('es_ES')
        purge = options.get('purge', False)
        self.verbosity = options.get('verbosity', 1)

        if purge:
            self.stdout.write('Purgando datos anteriores generados por el script...')
            # Borramos usuarios generados por el script (determinamos por dominio de email)
            usuarios = Usuario.objects.filter(email__iendswith='@faker.test')
            for u in usuarios:
                try:
                    u.delete()
                except Exception:
                    pass
            # También borrar funciones anteriores creadas por el script (marcadas por fecha: hace 30 +/- 7 días)
            cutoff_start = timezone.now() - timedelta(days=40)
            cutoff_end = timezone.now() - timedelta(days=20)
            Funcion.objects.filter(fecha_hora__gte=cutoff_start, fecha_hora__lte=cutoff_end).delete()
            self.stdout.write(self.style.SUCCESS('Purge completado.'))

        # PASO 1: Películas y Funciones (El Contexto)
        self.stdout.write('Creando géneros y películas...')
        terror, _ = Genero.objects.get_or_create(nombre='TERROR')
        comedia, _ = Genero.objects.get_or_create(nombre='COMEDIA')
        accion, _ = Genero.objects.get_or_create(nombre='ACCION')

        # Para evitar validaciones que prohíben fecha_estreno en el pasado, marcamos estreno en hoy
        hoy = date.today()

        pel_data = [
            ("La Monja 3", [terror], 95),
            ("Minions 5", [comedia], 90),
            ("Rápido y Furioso 20", [accion], 135),
        ]

        peliculas = {}
        for title, generos, dur in pel_data:
            pel, created = Pelicula.objects.get_or_create(
                titulo=title,
                defaults={
                    'sinopsis': fake.text(max_nb_chars=200),
                    'director': fake.name(),
                    'duracion': dur,
                    'fecha_estreno': hoy,
                    'clasificacion': 'ATP',
                    'es_estreno': False,
                }
            )
            # asegurar géneros
            for g in generos:
                pel.generos.add(g)
            pel.save()
            peliculas[title] = pel

        # Sala y butacas
        sala, _ = Sala.objects.get_or_create(numero=1, defaults={'nombre': 'Sala 1', 'activa': True})
        # Crear butacas si no existen suficientes
        needed_capacity = 120
        existing = Butaca.objects.filter(sala=sala, es_pasillo=False).count()
        if existing < needed_capacity:
            self.stdout.write(f'Creando butacas en {sala}...')
            new_butacas = []
            rows = [chr(i) for i in range(ord('A'), ord('A') + 10)]  # A-J
            for r in rows:
                for n in range(1, 13):  # 12 butacas por fila => 120
                    if not Butaca.objects.filter(sala=sala, fila=r, numero=n).exists():
                        new_butacas.append(Butaca(sala=sala, fila=r, numero=n, es_pasillo=False))
            Butaca.objects.bulk_create(new_butacas, batch_size=200)

        # Crear funciones pasadas (hace ~30 días)
        base_date = timezone.now() - timedelta(days=30)
        fechas = [base_date.date() + timedelta(days=i) for i in range(0, 7)]  # una semana alrededor de hace 1 mes

        funciones_to_create = []
        # Terror -> 22:00
        for fdate in fechas:
            dt = datetime.combine(fdate, time(hour=22, minute=0))
            funciones_to_create.append(Funcion(pelicula=peliculas['La Monja 3'], sala=sala, fecha_hora=dt, precio_base=120.00))
        # Comedia -> 15:00
        for fdate in fechas:
            dt = datetime.combine(fdate, time(hour=15, minute=0))
            funciones_to_create.append(Funcion(pelicula=peliculas['Minions 5'], sala=sala, fecha_hora=dt, precio_base=100.00))
        # Acción -> 20:00 (opcional)
        for fdate in fechas[:4]:
            dt = datetime.combine(fdate, time(hour=20, minute=0))
            funciones_to_create.append(Funcion(pelicula=peliculas['Rápido y Furioso 20'], sala=sala, fecha_hora=dt, precio_base=150.00))

        # Usar bulk_create para evitar validaciones de modelo que impiden fechas pasadas
        created_funcs = Funcion.objects.bulk_create(funciones_to_create, batch_size=50)

        # Recuperar funciones creadas (consultar por rango de fecha y sala)
        inicio = (base_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        fin = (base_date + timedelta(days=10)).replace(hour=23, minute=59, second=59, microsecond=999999)
        funciones = list(Funcion.objects.filter(fecha_hora__gte=inicio, fecha_hora__lte=fin, sala=sala).select_related('pelicula'))

        terror_funcs = [f for f in funciones if f.pelicula.titulo == 'La Monja 3']
        comedia_funcs = [f for f in funciones if f.pelicula.titulo == 'Minions 5']
        accion_funcs = [f for f in funciones if f.pelicula.titulo == 'Rápido y Furioso 20']

        # PASO 2: Crear 50 Clientes
        self.stdout.write('Creando 50 clientes de prueba...')
        clientes = []
        for i in range(50):
            username = f"testuser_{i}_{fake.user_name()}"
            email = f"{username}@faker.test"
            dni = str(10000000 + i)
            usuario, created = Usuario.objects.get_or_create(username=username, defaults={
                'email': email,
                'first_name': fake.first_name(),
                'last_name': fake.last_name(),
                'dni': dni,
                'rol': 'cliente'
            })
            if created:
                usuario.set_password('test1234')
                usuario.save()
            cliente_profile, _ = Cliente.objects.get_or_create(usuario=usuario)
            clientes.append({'usuario': usuario, 'perfil': cliente_profile})

        # PASO 3: Historial de Tickets
        self.stdout.write('Generando ventas y entradas para los grupos A/B/C...')

        # Helper: obtener butaca disponible para una función
        def obtener_butaca_disponible(func):
            used_ids = Entrada.objects.filter(id_funcion=func).values_list('id_butaca_id', flat=True)
            b = Butaca.objects.filter(sala=func.sala, es_pasillo=False).exclude(pk__in=list(used_ids)).first()
            return b

        # Grupo A: 10 clientes, 3 tickets cada uno, solo TERROR noche
        grupo_a = clientes[0:10]
        for c in grupo_a:
            venta = Venta.objects.create(id_cliente=c['perfil'], fecha_compra=base_date - timedelta(hours=random.randint(1,72)), tipo_venta='ONLINE', estado='CONFIRMADA')
            # Elegir funciones terror aleatorias dentro de terror_funcs
            chosen_funcs = random.choices(terror_funcs, k=3)
            for func in chosen_funcs:
                but = obtener_butaca_disponible(func)
                if not but:
                    continue
                Entrada.objects.create(id_venta=venta, id_funcion=func, id_sala=func.sala, id_butaca=but, id_pelicula=func.pelicula, estado='VENDIDA', reservado_por=c['usuario'])

        # Grupo B: 10 clientes, 3 tickets cada uno, solo COMEDIA tarde
        grupo_b = clientes[10:20]
        for c in grupo_b:
            venta = Venta.objects.create(id_cliente=c['perfil'], fecha_compra=base_date - timedelta(hours=random.randint(1,72)), tipo_venta='ONLINE', estado='CONFIRMADA')
            chosen_funcs = random.choices(comedia_funcs, k=3)
            for func in chosen_funcs:
                but = obtener_butaca_disponible(func)
                if not but:
                    continue
                Entrada.objects.create(id_venta=venta, id_funcion=func, id_sala=func.sala, id_butaca=but, id_pelicula=func.pelicula, estado='VENDIDA', reservado_por=c['usuario'])

        # Grupo C: 30 clientes, tickets aleatorios (1-4)
        grupo_c = clientes[20:50]
        todas_funcs = funciones
        for c in grupo_c:
            num_tickets = random.randint(1, 4)
            venta = Venta.objects.create(id_cliente=c['perfil'], fecha_compra=base_date - timedelta(hours=random.randint(1,72)), tipo_venta='ONLINE', estado='CONFIRMADA')
            for _ in range(num_tickets):
                func = random.choice(todas_funcs)
                but = obtener_butaca_disponible(func)
                if not but:
                    continue
                Entrada.objects.create(id_venta=venta, id_funcion=func, id_sala=func.sala, id_butaca=but, id_pelicula=func.pelicula, estado='VENDIDA', reservado_por=c['usuario'])

        self.stdout.write(self.style.SUCCESS('Población completa.'))
        # marcar tarea completada
        # (no vamos a modificar el todo list aquí programáticamente)
