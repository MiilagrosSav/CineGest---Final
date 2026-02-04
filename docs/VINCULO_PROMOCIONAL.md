# 📋 ANÁLISIS: VinculoPromocional (antes FuncionPromocion)

## 📅 Fecha
3 de febrero de 2026

## ✅ CONCLUSIÓN FINAL
**VinculoPromocional es ESENCIAL** para la arquitectura de promociones. Se ha renombrado y mejorado para mayor claridad y usabilidad.

---

## 🎯 PROPÓSITO DEL MODELO

`VinculoPromocional` es una **tabla intermedia explícita** (no ManyToManyField) que permite vincular promociones a:

1. **Películas específicas** (todas sus funciones)
2. **Funciones específicas** (solo esa proyección)

### Casos de Uso Reales

#### Ejemplo 1: Promoción por Película
```python
# Promoción "Recupero Terror" → Todas las funciones de "La Monja 3"
VinculoPromocional(
    promocion=promo_terror,
    pelicula=la_monja_3,
    funcion=None
)
```
**Efecto**: Cualquier función de "La Monja 3" obtiene la promoción automáticamente.

#### Ejemplo 2: Promoción por Función Específica
```python
# Promoción "Lunes Económico" → Solo Avengers del lunes 18:00
VinculoPromocional(
    promocion=promo_lunes,
    pelicula=None,
    funcion=avengers_lunes_18
)

# Avengers del lunes 21:00 → SIN promoción
```
**Efecto**: Permite granularidad por horario específico.

---

## 🏗️ ARQUITECTURA

### Niveles de Aplicación de Promociones

```
┌─────────────────────────────────────────────────────┐
│ NIVEL 1: Universal (genero_requerido)              │
│ Aplica a TODAS las películas de un género          │
│ Ejemplo: "20% off en todas las de acción"          │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│ NIVEL 2: Por Película (VinculoPromocional)         │
│ Aplica a TODAS las funciones de UNA película       │
│ Ejemplo: "2x1 en La Monja 3"                        │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│ NIVEL 3: Por Función (VinculoPromocional)          │
│ Aplica SOLO a UNA función específica               │
│ Ejemplo: "Descuento matinée 11:00"                 │
└─────────────────────────────────────────────────────┘
```

### Diferencia con genero_requerido

| Campo | Alcance | Ejemplo |
|-------|---------|---------|
| `genero_requerido` | TODAS las películas de un género | "20% off en terror" |
| `VinculoPromocional(pelicula=X)` | TODAS las funciones de UNA película | "2x1 en La Monja 3" |
| `VinculoPromocional(funcion=Y)` | UNA función específica | "Descuento lunes 18:00 Avengers" |

---

## 🔒 RESTRICCIONES DE INTEGRIDAD

### CheckConstraint: Exactamente Uno
```python
models.CheckConstraint(
    check=Q(pelicula__isnull=False, funcion__isnull=True) | 
          Q(pelicula__isnull=True, funcion__isnull=False),
    name='check_vinculo_exactamente_uno'
)
```

**Garantiza**:
- ✅ Solo película (función=NULL)
- ✅ Solo función (película=NULL)
- ❌ Ambos (rechazado)
- ❌ Ninguno (rechazado)

### UniqueConstraint
```python
models.UniqueConstraint(
    fields=['promocion', 'funcion', 'pelicula'],
    name='UQ_funcionpromocion_promocion_funcion_pelicula'
)
```

**Evita duplicados**: No se puede vincular la misma promoción a la misma película/función dos veces.

---

## 💻 IMPLEMENTACIÓN EN services.py

### Lógica de Validación (líneas 98-109)

```python
# Si la promoción tiene vínculos, verificar que aplique a esta función
tiene_vinculos = VinculoPromocional.objects.filter(promocion=p).exists()

if tiene_vinculos:
    # Buscar vínculo por función específica O por película
    vinculada = VinculoPromocional.objects.filter(promocion=p).filter(
        models.Q(funcion=funcion) | models.Q(pelicula=funcion.pelicula)
    ).exists()
    
    if not vinculada:
        # La promo tiene vínculos, pero no aplica a esta función/película
        continue
```

**Flujo**:
1. Si `VinculoPromocional` está vacío para la promoción → Aplica universalmente
2. Si `VinculoPromocional` tiene registros → Verificar si hay match con función o película
3. Si no hay match → Rechazar promoción

---

## 🎨 MEJORAS IMPLEMENTADAS

### 1. Renombrado del Modelo
- ❌ Antes: `FuncionPromocion` (confuso, suena solo a funciones)
- ✅ Ahora: `VinculoPromocional` (claro que vincula promociones)

### 2. Admin Interface Mejorado

#### Antes
```python
# Admin separado, difícil de usar
@admin.register(FuncionPromocion)
class FuncionPromocionAdmin(admin.ModelAdmin):
    # Usuario debe navegar a otra página
```

#### Ahora
```python
# Inline en PromocionAdmin (UX mejorado)
class VinculoPromocionalInline(admin.TabularInline):
    model = VinculoPromocional
    extra = 1
    fields = ('pelicula', 'funcion')
    verbose_name_plural = '🎯 Vínculos Específicos'

@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    inlines = [VinculoPromocionalInline]  # Gestión en una sola pantalla
```

**Beneficio**: Administrador crea promoción y vínculos en una sola pantalla.

### 3. CheckConstraint Agregado
```python
# NUEVO: Validación a nivel de base de datos
models.CheckConstraint(
    check=Q(pelicula__isnull=False, funcion__isnull=True) | 
          Q(pelicula__isnull=True, funcion__isnull=False),
    name='check_vinculo_exactamente_uno'
)
```

**Antes**: Solo validación en `clean()` (bypasseable con `save(skip_validation=True)`)
**Ahora**: Validación también en PostgreSQL (garantía de integridad)

### 4. Documentación Mejorada
```python
class VinculoPromocional(models.Model):
    """
    Tabla intermedia explícita que vincula una promoción con:
    - Una película específica (todas sus funciones), O
    - Una función específica (solo esa proyección)
    
    Casos de uso:
    - película != None, funcion = None → Aplica a TODAS las funciones de esa película
    - película = None, funcion != None → Aplica SOLO a esa función específica
    
    Ejemplo: Promoción "Lunes de Terror" activa para:
    - "La Monja 3" (todas las funciones) → pelicula_id=5, funcion=None
    - "Avengers" función del lunes 18:00 → pelicula=None, funcion_id=123
    - "Avengers" función del lunes 21:00 → SIN vínculo (NO aplica)
    """
```

---

## 📊 ESTADO ACTUAL EN PRODUCCIÓN

```bash
python scripts/verificar_uso_vinculo_promocional.py
```

**Resultado**:
```
📊 Registros en VinculoPromocional: 1
✅ LA TABLA SE ESTÁ USANDO

Primeros 5 registros:
  - Promo: Recupero Terror
    Función: N/A
    Película: La Monja 3
```

**Interpretación**: Promoción "Recupero Terror" vinculada a "La Monja 3" (todas sus funciones).

---

## ✅ TESTS DE VALIDACIÓN

### Script de Prueba
```bash
python scripts/test_vinculo_promocional_constraint.py
```

**Resultados**:
```
TEST 1: Crear vínculo sin película ni función
✅ ÉXITO: Validación rechazó el vínculo

TEST 2: Crear vínculo con película Y función
✅ ÉXITO: Validación rechazó el vínculo

TEST 3: Crear vínculo válido con SOLO película
✅ ÉXITO: Vínculo creado correctamente

TEST 4: Crear vínculo válido con SOLO función
✅ ÉXITO: Vínculo creado correctamente
```

---

## 📝 MIGRACIONES APLICADAS

### Migración 0020: Rename Model
```python
migrations.RenameModel(
    old_name='FuncionPromocion',
    new_name='VinculoPromocional',
)
```

**Operaciones**:
1. ✅ Renombrado de modelo en Django (NO toca DB)
2. ✅ Actualización de `related_name` en FKs
3. ✅ Agregado de `CheckConstraint`
4. ✅ Agregado de `verbose_name` y `verbose_name_plural`

**db_table**: Se mantiene como `promociones_funcionpromocion` para evitar migración de datos.

---

## 🎯 BEST PRACTICES APLICADAS

### 1. Tabla Intermedia Explícita (NO ManyToManyField)
```python
# ❌ MALO: Django ManyToManyField (menos control)
class Promocion(models.Model):
    funciones = models.ManyToManyField('cine.Funcion')

# ✅ BUENO: Tabla intermedia explícita (control total)
class VinculoPromocional(models.Model):
    promocion = models.ForeignKey(Promocion, ...)
    funcion = models.ForeignKey('cine.Funcion', null=True, ...)
    pelicula = models.ForeignKey('cine.Pelicula', null=True, ...)
```

**Ventajas**:
- Permite FKs nullable (película O función)
- Permite agregar campos adicionales si es necesario
- CheckConstraints personalizados
- Validación explícita en `clean()`

### 2. CheckConstraint + Validación en Modelo
```python
# Nivel 1: Validación en base de datos (PostgreSQL)
models.CheckConstraint(...)

# Nivel 2: Validación en modelo (Django admin/forms)
def clean(self):
    if not self.funcion and not self.pelicula:
        raise ValidationError(...)
```

**Defensa en profundidad**: Doble validación para máxima seguridad.

### 3. Admin UX con Inline
```python
class VinculoPromocionalInline(admin.TabularInline):
    model = VinculoPromocional
    extra = 1

@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    inlines = [VinculoPromocionalInline]
```

**Beneficio**: Gestión centralizada en una sola pantalla.

---

## 📖 RECOMENDACIONES FUTURAS

### 1. Agregar Campo de Prioridad (Opcional)
```python
class VinculoPromocional(models.Model):
    prioridad = models.IntegerField(default=0)  # Mayor = más prioritario
```

**Caso de uso**: Si una función tiene vínculo por película Y por función, elegir cuál aplicar.

### 2. Agregar Fechas de Vigencia (Opcional)
```python
class VinculoPromocional(models.Model):
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
```

**Caso de uso**: Vínculo temporal ("Solo funciones de diciembre").

### 3. Caché de Vínculos (Performance)
```python
from django.core.cache import cache

def get_vinculos_promocion(promocion_id):
    cache_key = f'vinculos_promo_{promocion_id}'
    vinculos = cache.get(cache_key)
    
    if vinculos is None:
        vinculos = list(VinculoPromocional.objects.filter(
            promocion_id=promocion_id
        ).values_list('funcion_id', 'pelicula_id'))
        cache.set(cache_key, vinculos, 300)  # 5 minutos
    
    return vinculos
```

---

## 🔍 RESUMEN EJECUTIVO

| Aspecto | Estado |
|---------|--------|
| **Propósito** | ✅ Vincular promociones a películas/funciones específicas |
| **Arquitectura** | ✅ Tabla intermedia explícita (best practice) |
| **Integridad** | ✅ CheckConstraint + UniqueConstraint |
| **UX** | ✅ Inline en PromocionAdmin |
| **Documentación** | ✅ Docstrings detallados + comentarios |
| **Tests** | ✅ Script de validación con 4 casos |
| **Producción** | ✅ 1 registro activo ("Recupero Terror") |
| **Migraciones** | ✅ Aplicadas sin errores |

---

## 💡 CONCLUSIÓN

`VinculoPromocional` es un componente **esencial** del sistema de promociones que permite:

1. ✅ **Granularidad fina**: Promociones por película O por función
2. ✅ **Arquitectura sólida**: Tabla intermedia explícita con constraints
3. ✅ **UX mejorada**: Gestión inline en admin
4. ✅ **Integridad garantizada**: CheckConstraint a nivel de DB

**Recomendación**: ✅ MANTENER Y CONTINUAR USANDO

---

**Documentado por**: GitHub Copilot (Claude Sonnet 4.5)  
**Fecha**: 3 de febrero de 2026  
**Validado para**: Django 5.2.6 + PostgreSQL
