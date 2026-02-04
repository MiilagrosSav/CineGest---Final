# 🎯 Guía de Uso: Vínculos Promocionales

## 📅 Actualizado
3 de febrero de 2026

---

## 🎨 Cambios en la Interfaz HTML

### 1. Formulario de Promoción (promocion_form.html)

#### ✅ Nuevo Panel de Vínculos (Solo al Editar)

Cuando editas una promoción existente, ahora verás un panel informativo:

```html
🎯 Vínculos Específicos a Películas/Funciones

Para vincular esta promoción a películas específicas o funciones 
individuales, utiliza el panel de administración de Django.

💡 Niveles de aplicación:
  • Universal: Género requerido → Todas las películas del género
  • Por Película: Admin → Vínculos → Todas las funciones de UNA película
  • Por Función: Admin → Vínculos → Solo UNA función específica

[⚙️ Abrir en Admin (Vínculos)]
```

**Ubicación**: Aparece después del checkbox "Aplicación automática"

**Función**: 
- Informa al usuario sobre los vínculos específicos
- Proporciona un botón directo al admin de Django
- Explica los 3 niveles de aplicación de promociones

---

### 2. Lista de Promociones (_promocion_table.html)

#### ✅ Nueva Columna: Vínculos

Se agregó una columna "Vínculos" que muestra:

| Estado | Visualización | Descripción |
|--------|---------------|-------------|
| **Sin vínculos** | `Universal` (gris) | Aplica según género/días configurados |
| **Con vínculos** | `🎯 2` (verde) | Tiene 2 vínculo(s) específico(s) |

**Ejemplo visual**:
```
┌────────┬────────┬────────┬───────────┬─────────┬──────────┬────────┬──────────┬─────────┐
│ Tipo   │ Código │ Nombre │ Descuento │ Días    │ Estrenos │ Género │ Vínculos │ Vigencia│
├────────┼────────┼────────┼───────────┼─────────┼──────────┼────────┼──────────┼─────────┤
│🛒 AUTO │ TERROR │ 20% Terror│ 20%    │ Todos   │ ✅ Sí   │ Terror │ 🎯 1     │ ...     │
│🛒 AUTO │ LUNES  │ Lunes 2x1│ 2x1     │ Lu      │ ⛔ No   │ Todos  │ Universal│ ...     │
└────────┴────────┴────────┴───────────┴─────────┴──────────┴────────┴──────────┴─────────┘
```

**Tooltip al pasar el mouse**:
- Sin vínculos: "Sin vínculos específicos (aplica universalmente)"
- Con vínculos: "Tiene 2 vínculo(s) específico(s)"

---

### 3. Vista PromocionListView (views.py)

#### ✅ Optimización de Query

Se agregó `prefetch_related('vinculos')` para evitar N+1 queries:

```python
def get_queryset(self):
    qs = super().get_queryset()
    qs = qs.prefetch_related('vinculos')  # ← NUEVO
    # ... resto del código
```

**Impacto**: Reduce queries de N+1 a 2 queries totales (1 para promociones + 1 para vínculos).

---

## 🔄 Flujo de Trabajo para el Usuario

### Crear Promoción con Vínculos Específicos

1. **Crear Promoción Base**
   ```
   Promociones → Crear Nueva
   - Código: RECUPERO_TERROR
   - Nombre: Recupero de Terror
   - Tipo: 2x1
   - Automática: ✅ Sí
   - Guardar
   ```

2. **Agregar Vínculos**
   ```
   Aparecerá panel "Vínculos Específicos"
   → Clic en [⚙️ Abrir en Admin (Vínculos)]
   
   En Admin de Django:
   → Scroll hasta "Vínculos Específicos"
   → Agregar vínculo:
      - Película: La Monja 3 (dejar Función vacío)
   → Guardar
   ```

3. **Resultado**
   - Promoción "Recupero de Terror" se aplica a TODAS las funciones de "La Monja 3"
   - En lista de promociones: Mostrará "🎯 1"

---

### Ejemplo Práctico: Promoción por Horario

**Caso**: Descuento solo en función de lunes 18:00

1. **Crear Promoción**
   ```
   - Código: LUNES_TARDE
   - Nombre: Lunes Económico
   - Tipo: PORCENTAJE (20%)
   - Automática: ✅ Sí
   - Días: Lunes ✅
   ```

2. **Vincular a Función Específica**
   ```
   Admin → Vínculos:
   - Función: Avengers - Lunes 18:00 (dejar Película vacío)
   ```

3. **Comportamiento**
   - ✅ Avengers lunes 18:00 → 20% descuento
   - ❌ Avengers lunes 21:00 → Sin descuento
   - ❌ Avengers martes 18:00 → Sin descuento

---

## 🎯 Diferencias entre Niveles

### Nivel 1: Universal (Género Requerido)

**Configuración**: 
```
Género requerido: Terror
Vínculos: (vacío)
```

**Aplica a**: 
- ✅ TODAS las películas de terror
- ✅ TODAS las funciones de esas películas

**Visualización**: 
```
Género: Terror
Vínculos: Universal
```

---

### Nivel 2: Por Película

**Configuración**: 
```
Género requerido: (vacío)
Vínculos: 
  - Película: La Monja 3
```

**Aplica a**: 
- ✅ TODAS las funciones de "La Monja 3"
- ❌ Otras películas de terror

**Visualización**: 
```
Género: Todos
Vínculos: 🎯 1
```

---

### Nivel 3: Por Función Específica

**Configuración**: 
```
Género requerido: (vacío)
Vínculos: 
  - Función: La Monja 3 - Lunes 18:00
```

**Aplica a**: 
- ✅ SOLO función de lunes 18:00 de "La Monja 3"
- ❌ La Monja 3 lunes 21:00
- ❌ La Monja 3 martes 18:00

**Visualización**: 
```
Género: Todos
Vínculos: 🎯 1
```

---

## 🎨 Estilos CSS Agregados

### Archivo: promocion_list.css

```css
/* Indicador de vínculos */
.vinculo-indicator {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.6rem;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    background: rgba(78, 205, 196, 0.15);
    color: #4ecdc4;
    border: 1px solid rgba(78, 205, 196, 0.3);
}

/* Estado universal (sin vínculos) */
.vinculo-indicator.universal {
    background: rgba(170, 170, 170, 0.1);
    color: #999;
    border: 1px solid rgba(170, 170, 170, 0.2);
    font-weight: 400;
}
```

---

## ✅ Archivos Modificados

### Templates
- ✅ `promociones/templates/promociones/promocion_form.html`
  - Agregado panel informativo de vínculos (líneas 153-182)
  - Botón directo al admin de Django

- ✅ `promociones/templates/promociones/_promocion_table.html`
  - Agregada columna "Vínculos" en header (línea 10)
  - Agregada celda con contador de vínculos (líneas 93-107)

### Vistas
- ✅ `promociones/views.py`
  - Agregado `prefetch_related('vinculos')` en PromocionListView

### Estilos
- ✅ `promociones/static/promociones/css/promocion_list.css`
  - Agregados estilos `.vinculo-indicator` y `.vinculo-indicator.universal`

---

## 🧪 Cómo Probar

### 1. Verificar Panel en Formulario

```bash
# Acceder a edición de promoción existente
http://localhost:8000/promociones/promociones/1/editar/

# Debe mostrar:
✅ Panel "Vínculos Específicos" (azul claro)
✅ Botón "⚙️ Abrir en Admin (Vínculos)"
```

### 2. Verificar Columna en Lista

```bash
# Acceder a lista de promociones
http://localhost:8000/promociones/promociones/

# Debe mostrar:
✅ Nueva columna "Vínculos"
✅ "Universal" para promociones sin vínculos
✅ "🎯 N" para promociones con N vínculos
```

### 3. Verificar Conteo de Vínculos

```bash
# Crear vínculo en admin
http://localhost:8000/admin/promociones/promocion/1/change/

# Scroll hasta "Vínculos Específicos"
# Agregar película o función
# Guardar

# Volver a lista de promociones
# Debe mostrar "🎯 1"
```

---

## 📊 Resumen de Cambios

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `promocion_form.html` | Template | Panel informativo de vínculos |
| `_promocion_table.html` | Template | Columna "Vínculos" con contador |
| `views.py` | Vista | `prefetch_related('vinculos')` |
| `promocion_list.css` | CSS | Estilos para `.vinculo-indicator` |

**Total**: 4 archivos modificados

---

## 💡 Notas Importantes

### ⚠️ Acceso al Admin

El botón "Abrir en Admin" requiere:
- Usuario con permisos de admin
- Django admin habilitado en `/admin/`
- Sesión activa en el admin

Si el usuario no tiene acceso, el botón abrirá la página de login del admin.

### 🎯 Tooltips

Los tooltips se muestran al pasar el mouse sobre:
- "Universal" → "Sin vínculos específicos (aplica universalmente)"
- "🎯 2" → "Tiene 2 vínculo(s) específico(s)"

### 🔄 Actualización Automática

El contador de vínculos se actualiza automáticamente al:
- Agregar vínculos desde el admin
- Eliminar vínculos desde el admin
- Recargar la página de lista de promociones

---

## ✅ Checklist de Implementación

- [x] Panel informativo en formulario de edición
- [x] Botón directo al admin de Django
- [x] Columna "Vínculos" en tabla de promociones
- [x] Contador de vínculos (🎯 N)
- [x] Estilos CSS para indicadores
- [x] Optimización de queries (prefetch_related)
- [x] Tooltips informativos
- [x] Documentación HTML completa

**Estado**: ✅ IMPLEMENTACIÓN COMPLETA

---

**Documentado por**: GitHub Copilot (Claude Sonnet 4.5)  
**Fecha**: 3 de febrero de 2026  
**Versión**: 1.0.0
