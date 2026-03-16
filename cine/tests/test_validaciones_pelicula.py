"""
Script de Prueba - Validación de Integridad del Modelo Película

Este script demuestra cómo las validaciones implementadas en el método save()
protegen la integridad de los datos contra manipulaciones externas.

⚠️ ADVERTENCIA: Este script es solo para fines educativos y de prueba.
"""

from django.core.exceptions import ValidationError
from datetime import date, timedelta
from cine.models import Clasificacion


def _get_clasificacion_atp():
    """Helper para obtener clasificación ATP"""
    clasificacion, _ = Clasificacion.objects.get_or_create(
        nombre='ATP',
        defaults={
            'descripcion': 'Apta para todo público',
            'edad_minima': 0,
            'orden': 1
        }
    )
    return clasificacion


def _get_clasificacion_13():
    """Helper para obtener clasificación +13"""
    clasificacion, _ = Clasificacion.objects.get_or_create(
        nombre='+13',
        defaults={
            'descripcion': 'Apta para mayores de 13 años',
            'edad_minima': 13,
            'orden': 2
        }
    )
    return clasificacion


def test_validacion_titulo_numero():
    """
    Prueba 1: Intentar guardar un título que sea un número

    ❌ Debe fallar: El título no puede ser un número
    """
    print("\n" + "="*70)
    print("PRUEBA 1: Validación de Título Numérico")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='123',  # ❌ Título numérico
            sinopsis='Una película de prueba',
            director='Christopher Nolan',
            duracion=120,
            fecha_estreno=date.today() + timedelta(days=30),
            clasificacion=_get_clasificacion_atp()
        )
        pelicula.save()

        print("❌ ERROR: La película con título numérico '123' se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó el título numérico")
        print(f"   Mensaje: {e.message_dict.get('titulo', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_validacion_titulo_numero_negativo():
    """
    Prueba 2: Intentar guardar un título con número negativo

    ❌ Debe fallar: El título no puede ser un número negativo
    """
    print("\n" + "="*70)
    print("PRUEBA 2: Validación de Título con Número Negativo")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='-456',  # ❌ Número negativo
            sinopsis='Una película de prueba',
            director='Martin Scorsese',
            duracion=150,
            fecha_estreno=date.today() + timedelta(days=60),
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print("❌ ERROR: La película con título '-456' se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó el título con número negativo")
        print(f"   Mensaje: {e.message_dict.get('titulo', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_validacion_director_numero():
    """
    Prueba 3: Intentar guardar un director que sea un número

    ❌ Debe fallar: El director no puede ser un número
    """
    print("\n" + "="*70)
    print("PRUEBA 3: Validación de Director Numérico")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='Inception',
            sinopsis='Una película de prueba',
            director='789',  # ❌ Director numérico
            duracion=148,
            fecha_estreno=date.today() + timedelta(days=15),
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print("❌ ERROR: La película con director numérico '789' se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó el director numérico")
        print(f"   Mensaje: {e.message_dict.get('director', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_validacion_director_numero_negativo():
    """
    Prueba 4: Intentar guardar un director con número negativo

    ❌ Debe fallar: El director no puede ser un número negativo
    """
    print("\n" + "="*70)
    print("PRUEBA 4: Validación de Director con Número Negativo")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='The Dark Knight',
            sinopsis='Una película de prueba',
            director='-999',  # ❌ Número negativo
            duracion=152,
            fecha_estreno=date.today() + timedelta(days=20),
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print("❌ ERROR: La película con director '-999' se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó el director con número negativo")
        print(f"   Mensaje: {e.message_dict.get('director', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_validacion_fecha_pasado():
    """
    Prueba 5: Intentar guardar una fecha de estreno en el pasado

    ❌ Debe fallar: La fecha no puede ser anterior a hoy
    """
    print("\n" + "="*70)
    print("PRUEBA 5: Validación de Fecha de Estreno en el Pasado")
    print("="*70)

    from cine.models import Pelicula

    try:
        fecha_pasada = date.today() - timedelta(days=100)

        pelicula = Pelicula(
            titulo='Avengers: Endgame',
            sinopsis='Una película de prueba',
            director='Anthony Russo',
            duracion=181,
            fecha_estreno=fecha_pasada,  # ❌ Fecha en el pasado
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print(f"❌ ERROR: La película con fecha {fecha_pasada} se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó la fecha en el pasado")
        print(f"   Mensaje: {e.message_dict.get('fecha_estreno', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_validacion_fecha_ayer():
    """
    Prueba 6: Intentar guardar una fecha de estreno de ayer

    ❌ Debe fallar: La fecha no puede ser de ayer
    """
    print("\n" + "="*70)
    print("PRUEBA 6: Validación de Fecha de Estreno de Ayer")
    print("="*70)

    from cine.models import Pelicula

    try:
        fecha_ayer = date.today() - timedelta(days=1)

        pelicula = Pelicula(
            titulo='Spider-Man: No Way Home',
            sinopsis='Una película de prueba',
            director='Jon Watts',
            duracion=148,
            fecha_estreno=fecha_ayer,  # ❌ Fecha de ayer
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print(f"❌ ERROR: La película con fecha {fecha_ayer} se guardó (NO DEBERÍA)")

    except ValidationError as e:
        print("✅ ÉXITO: El sistema rechazó la fecha de ayer")
        print(f"   Mensaje: {e.message_dict.get('fecha_estreno', [e])[0]}")
    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_limpieza_espacios():
    """
    Prueba 7: Verificar limpieza automática de espacios

    ✅ Debe funcionar: El sistema limpia espacios automáticamente
    """
    print("\n" + "="*70)
    print("PRUEBA 7: Limpieza Automática de Espacios")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='  Interstellar  ',  # Con espacios
            sinopsis='Una película de prueba',
            director='  Christopher Nolan  ',  # Con espacios
            duracion=169,
            fecha_estreno=date.today() + timedelta(days=45),
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        # Verificar que se limpiaron los espacios
        pelicula.refresh_from_db()

        if pelicula.titulo == 'Interstellar' and pelicula.director == 'Christopher Nolan':
            print("✅ ÉXITO: Los espacios se limpiaron automáticamente")
            print(f"   Título guardado: '{pelicula.titulo}'")
            print(f"   Director guardado: '{pelicula.director}'")
        else:
            print(f"❌ ERROR: Los espacios no se limpiaron correctamente")
            print(f"   Título: '{pelicula.titulo}'")
            print(f"   Director: '{pelicula.director}'")

        # Limpiar la película de prueba
        pelicula.delete()

    except Exception as e:
        print(f"⚠️  Error inesperado: {e}")


def test_pelicula_valida():
    """
    Prueba 8: Verificar que películas válidas SÍ se guarden correctamente

    ✅ Debe funcionar: Una película válida debe guardarse sin problemas
    """
    print("\n" + "="*70)
    print("PRUEBA 8: Guardado de Película Válida")
    print("="*70)

    from cine.models import Pelicula

    try:
        pelicula = Pelicula(
            titulo='The Matrix',
            sinopsis='Una película de ciencia ficción sobre realidad virtual',
            director='Lana Wachowski',
            duracion=136,
            fecha_estreno=date.today() + timedelta(days=90),
            clasificacion=_get_clasificacion_13()
        )
        pelicula.save()

        print("✅ ÉXITO: La película válida se guardó correctamente")
        print(f"   ID: {pelicula.pk}")
        print(f"   Título: '{pelicula.titulo}'")
        print(f"   Director: '{pelicula.director}'")
        print(f"   Fecha: {pelicula.fecha_estreno}")

        # Limpiar la película de prueba
        pelicula.delete()

    except Exception as e:
        print(f"❌ ERROR: La película válida no se guardó: {e}")


def run_all_tests():
    """Ejecuta todas las pruebas de validación"""
    print("\n" + "="*70)
    print(" "*15 + "SUITE DE PRUEBAS DE INTEGRIDAD")
    print(" "*18 + "App: Cine - Modelo Película")
    print("="*70)

    test_validacion_titulo_numero()
    test_validacion_titulo_numero_negativo()
    test_validacion_director_numero()
    test_validacion_director_numero_negativo()
    test_validacion_fecha_pasado()
    test_validacion_fecha_ayer()
    test_limpieza_espacios()
    test_pelicula_valida()

    print("\n" + "="*70)
    print(" "*20 + "FIN DE PRUEBAS")
    print("="*70 + "\n")


if __name__ == '__main__':
    run_all_tests()
