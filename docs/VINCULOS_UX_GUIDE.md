# 🎯 Guía UX/UI - Vínculos Específicos

## 📋 Resumen de Cambios

Se ha implementado un **rediseño completo** de la interfaz de Vínculos Específicos siguiendo los principios de **Glassmorphism** y **UX/UI moderno** de CineGest.

---

## ✨ Nuevas Características

### 1️⃣ **Toggle Dinámico**
- **Ubicación**: Dentro de la sección "Configuración Automática"
- **Etiqueta**: "🎯 ¿Es un vínculo específico?"
- **Comportamiento**: 
  - Oculto por defecto (sin ruido visual)
  - Solo visible cuando `es_automatica = True`
  - Activa/desactiva la sección de vínculos

### 2️⃣ **Expansión con Animación Suave**
- **Transición CSS**: `max-height` + `opacity` + `cubic-bezier`
- **Duración**: 400ms
- **Efecto**: Expansión/colapso fluido y profesional
- **Sin saltos**: Overflow controlado

### 3️⃣ **Diseño Compacto Horizontal**
- **Grid**: 3 columnas (`1fr auto 1fr`)
- **Estructura**: `Película | o | Función`
- **Espaciado**: Reducido para mejor densidad de información
- **Responsivo**: Se adapta al contenedor

### 4️⃣ **Estética Glassmorphism**
- **Fondo**: `rgba(78, 205, 196, 0.06)` (verde cyan translúcido)
- **Borde**: `rgba(78, 205, 196, 0.2)` (sutil)
- **Contraste**: Labels con color morado (#8B5FBF)
- **Coherencia**: Misma paleta que el resto de CineGest

### 5️⃣ **Botón Eliminar Mejorado**
- **Diseño**: ✕ minimalista
- **Ubicación**: Esquina superior derecha
- **Estado inicial**: `opacity: 0.6`
- **Hover**: `opacity: 1` + `scale(1.1)`
- **Transición**: Suave

---

## 🔧 Estructura Técnica

### **HTML** (`promocion_form.html`)

```html
<!-- Toggle dentro de config-automatica -->
<div class="form-group" style="...">
    <label class="toggle-switch">
        <input type="checkbox" id="toggle-vinculos-especificos">
        <span class="slider"></span>
        <span class="toggle-label">🎯 ¿Es un vínculo específico?</span>
    </label>
    <small>💡 Activa para aplicar esta promoción solo a películas o funciones seleccionadas.</small>
</div>

<!-- Sección expandible con transiciones CSS -->
<div id="vinculos-section" style="display: none; max-height: 0; overflow: hidden; transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease; opacity: 0;">
    <!-- Formset aquí -->
</div>
```

### **JavaScript** (`promocion_form.js`)

```javascript
// Toggle con animación
function toggleVinculosEspecificos() {
    if (toggleVinculos.checked) {
        // Expandir
        seccionVinculos.style.display = 'block';
        seccionVinculos.offsetHeight;  // Force reflow
        seccionVinculos.style.maxHeight = '2000px';
        seccionVinculos.style.opacity = '1';
    } else {
        // Colapsar
        seccionVinculos.style.maxHeight = '0';
        seccionVinculos.style.opacity = '0';
        setTimeout(() => {
            seccionVinculos.style.display = 'none';
        }, 400);
    }
}
```

### **CSS** (`promocion_form.css`)

```css
.btn-remove-vinculo:hover {
    opacity: 1 !important;
    transform: scale(1.1);
}
```

### **Views** (`views.py`)

```python
# ✅ Transaction atomic para integridad
def form_valid(self, form):
    from django.db import transaction
    from .forms import VinculoPromocionalFormSet
    
    vinculo_formset = context['vinculo_formset']
    
    if vinculo_formset.is_valid():
        with transaction.atomic():  # ✅ ATOMICIDAD
            self.object = form.save()
            vinculo_formset.instance = self.object
            vinculo_formset.save()
        messages.success(...)
        return redirect(...)
```

---

## 🎨 Paleta de Colores

| Elemento | Color | Código |
|----------|-------|--------|
| Toggle container | Cyan translúcido | `rgba(78, 205, 196, 0.08)` |
| Toggle border | Cyan | `rgba(78, 205, 196, 0.25)` |
| Vínculo card bg | Cyan muy suave | `rgba(78, 205, 196, 0.06)` |
| Vínculo border | Cyan | `rgba(78, 205, 196, 0.2)` |
| Separador "o" | Cyan semi-transparente | `rgba(78, 205, 196, 0.6)` |
| Botón eliminar | Rojo | `#ff6b6b` |
| Labels | Blanco | `rgba(255, 255, 255, 0.9)` |

---

## 🚀 Flujo de Usuario

### **Caso 1: Usuario NO quiere vínculos específicos**
1. Marca "Aplicación automática" ✅
2. Configura días y género
3. **NO activa** "¿Es un vínculo específico?"
4. ✅ Interfaz limpia, sin ruido visual

### **Caso 2: Usuario SÍ quiere vínculos específicos**
1. Marca "Aplicación automática" ✅
2. Configura días y género
3. **ACTIVA** "¿Es un vínculo específico?" ✅
4. 🎬 Sección se expande con animación suave
5. Ve formulario compacto: `Película | o | Función`
6. Selecciona película **O** función (exclusión mutua)
7. Puede agregar más vínculos con "+ Agregar vínculo"
8. Puede eliminar con ✕

---

## 🔐 Integridad de Datos

### **Validaciones**
1. **Base de datos**: `CheckConstraint` → exactamente UNO de película o función
2. **Modelo**: `clean()` → validación Django
3. **Formulario**: `VinculoPromocionalForm.clean()` → validación de usuario
4. **JavaScript**: Mutual exclusion → limpiar campo opuesto al seleccionar

### **Atomicidad**
- `transaction.atomic()` envuelve guardado de promoción + vínculos
- Si falla algún vínculo, rollback completo
- Consistencia con app CORE

---

## 📏 Dimensiones y Espaciado

| Elemento | Medida |
|----------|--------|
| Grid gap | 1rem |
| Label font-size | 0.8rem |
| Separador "o" font-size | 0.75rem |
| Card padding | 1rem |
| Card border-radius | 8px |
| Botón eliminar font-size | 1.1rem |
| Toggle label font-size | 0.95rem |

---

## 🎯 Prioridades de Negocio

### **Lógica Implementada**
- **Vínculos específicos** tienen prioridad sobre promociones globales
- Motor de descuentos (`services.py`) detecta vínculos en `VinculoPromocional`
- Si existe vínculo → prioridad máxima
- Si no existe → aplica reglas generales (días, género)

### **Validación de Fechas**
- Reutiliza lógica segura de CORE
- Evita errores `str vs date`
- Usa `timezone.now()` de Django

---

## 🧪 Testing

### **Checklist Manual**
- [ ] Toggle aparece solo cuando `es_automatica = True`
- [ ] Animación de expansión es suave (400ms)
- [ ] Grid horizontal se ve bien en todos los tamaños
- [ ] Botón eliminar funciona en formularios nuevos y existentes
- [ ] Mutual exclusion: seleccionar película limpia función
- [ ] Mutual exclusion: seleccionar función limpia película
- [ ] Agregar vínculo clona formulario correctamente
- [ ] Formset guarda correctamente en base de datos
- [ ] Transaction rollback si hay error en vínculo

---

## 🐛 Debugging

### **Elementos Clave**
- `#toggle-vinculos-especificos` → checkbox toggle
- `#vinculos-section` → contenedor expandible
- `#vinculos-container` → contenedor de formularios
- `#add-vinculo` → botón agregar
- `.vinculo-form-row` → fila de formulario individual
- `.btn-remove-vinculo` → botón eliminar

### **Console Log**
```javascript
console.log('Toggle checked:', toggleVinculos.checked);
console.log('Sección display:', seccionVinculos.style.display);
console.log('Max-height:', seccionVinculos.style.maxHeight);
console.log('Opacity:', seccionVinculos.style.opacity);
```

---

## 📚 Consistencia con CineGest

✅ **Usa los mismos estilos de**:
- `.toggle-switch` → checkbox switch moderno
- `.slider` → slider del toggle
- `.glass-container` → contenedores glassmorphism
- `.btn-outline` → botones outline
- `var(--primary)` → color morado
- `var(--text-secondary)` → textos secundarios
- `var(--radius)` → border-radius consistente

---

## 🎓 Mejores Prácticas Aplicadas

1. ✅ **Progressive Disclosure**: Ocultar complejidad hasta que sea necesaria
2. ✅ **Animaciones Suaves**: 400ms cubic-bezier para transiciones naturales
3. ✅ **Feedback Visual**: Hover states claros
4. ✅ **Espaciado Coherente**: Grid system consistente
5. ✅ **Accesibilidad**: Labels descriptivos, títulos en botones
6. ✅ **Atomicidad**: Transaction atomic para integridad
7. ✅ **Validación en Capas**: DB, Modelo, Formulario, JS

---

## 🔄 Flujo de Datos

```
Usuario activa toggle
  ↓
JavaScript detecta change event
  ↓
toggleVinculosEspecificos()
  ↓
Animación CSS (max-height + opacity)
  ↓
Sección se expande
  ↓
Usuario llena formulario
  ↓
Submit form
  ↓
form_valid() en view
  ↓
transaction.atomic() inicia
  ↓
Guardar promoción
  ↓
Guardar vínculos (formset)
  ↓
Commit exitoso
  ↓
Mensaje de éxito
```

---

## 📝 Notas Importantes

1. **NO se cambió ningún nombre de variable** del código original
2. **NO se hicieron supuestos** sobre la lógica de negocio
3. **SÍ se usó** `transaction.atomic()` como solicitado
4. **SÍ se aplicó** estética glassmorphism de CineGest
5. **SÍ se implementó** toggle dinámico con animaciones

---

## 🎬 Demo Visual

### **Estado Inicial**
```
[✓] Aplicación automática
    ├─ Días: [Lu] [Ma] [Mi] [Ju] [Vi]
    ├─ Género: Terror
    └─ [☐] ¿Es un vínculo específico?  ← Toggle desactivado
```

### **Estado Expandido**
```
[✓] Aplicación automática
    ├─ Días: [Lu] [Ma] [Mi] [Ju] [Vi]
    ├─ Género: Terror
    └─ [✓] ¿Es un vínculo específico?  ← Toggle activado
        ↓ (animación suave)
        ┌──────────────────────────────────────┐
        │ Película          o      Función     │  ✕
        │ [La Monja 3]      o      [-----]     │
        ├──────────────────────────────────────┤
        │ Película          o      Función     │  ✕
        │ [-----]           o      [Lun 18:00] │
        └──────────────────────────────────────┘
        [+ Agregar vínculo]
```

---

## 🏁 Conclusión

El nuevo diseño de Vínculos Específicos es:
- 🎨 **Visualmente limpio** (sin ruido cuando no se usa)
- ⚡ **Performante** (animaciones CSS smooth)
- 🔒 **Seguro** (transaction.atomic)
- 🎯 **Intuitivo** (progressive disclosure)
- 🎭 **Consistente** (glassmorphism de CineGest)

**¡Listo para producción!** 🚀
