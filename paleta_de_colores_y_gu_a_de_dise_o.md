# Guía de estilo y paleta de colores FIPCA

Paleta digital basada en la imagen `nueva_paleta_de_colores.jpeg`. La identidad
se construye con el azul profundo del tapete, sus planos cobalto, los destellos
cian y el violeta del extremo derecho. En las aplicaciones, los detalles de
marca se representan en azul brillante, no en tonos metálicos.

## Colores de marca

| Muestra | Nombre | HEX | Uso |
| :---: | :--- | :--- | :--- |
| <span style="color:#1B2450; font-size:20px;">████</span> | Azul noche | `#1B2450` | Fondos profundos y texto principal |
| <span style="color:#303F76; font-size:20px;">████</span> | Azul profundo | `#303F76` | Superficies de marca y conversación |
| <span style="color:#405080; font-size:20px;">████</span> | Azul pizarra | `#405080` | Planos geométricos y transiciones |
| <span style="color:#2563EB; font-size:20px;">████</span> | Azul cobalto | `#2563EB` | Acciones principales y enlaces |
| <span style="color:#7DD3FC; font-size:20px;">████</span> | Azul cielo | `#7DD3FC` | Acento de marca y acciones en modo oscuro |
| <span style="color:#2CB6C8; font-size:20px;">████</span> | Cian | `#2CB6C8` | Detalles puntuales inspirados en los brillos del tapete |
| <span style="color:#6B46C1; font-size:20px;">████</span> | Violeta | `#6B46C1` | Acento secundario y foco en modo claro |
| <span style="color:#805AD5; font-size:20px;">████</span> | Violeta claro | `#805AD5` | Reflejos y degradados de marca |
| <span style="color:#FFFFFF; font-size:20px;">████</span> | Blanco | `#FFFFFF` | Logotipo y texto sobre fondos oscuros |

El fondo geométrico de la imagen combina azules índigo y cobalto con zonas
violetas y puntos cian. La madera, el teclado, la maceta y la papelería son
elementos de ambientación de la fotografía; no son colores de la interfaz.

## Colores funcionales de interfaz

| Rol | Modo claro | Modo oscuro |
| :--- | :--- | :--- |
| Fondo | `#F4F7FB` | `#121B2A` |
| Superficie | `#FFFFFF` | `#1B263B` |
| Superficie alterna | `#EEF3F8` | `#22334B` |
| Borde | `#D9E2EC` | `#35465D` |
| Texto principal | `#172338` | `#F2F5FA` |
| Texto suave | `#4A5568` | `#C0CBD9` |
| Fondo de acción | `#2563EB` | `#7DD3FC` |
| Texto de acción | `#FFFFFF` | `#10213F` |
| Superficie de acento | `#EFF6FF` | `#172B4D` |
| Texto de acento | `#1D4ED8` | `#BFDBFE` |
| Foco visible | `#6B46C1` | `#7DD3FC` |
| Éxito | `#2F6B4F` sobre `#EAF4EE` | `#8FD0AD` sobre `#1C2A24` |
| Error | `#A12632` sobre `#FFF0EF` | `#FFB4AB` sobre `#401E22` |

## Reglas de uso

- El azul cobalto identifica las acciones principales en modo claro; el azul
  cielo mantiene su legibilidad en modo oscuro.
- El azul profundo organiza superficies y jerarquía; cian y violeta son acentos,
  no sustituyen los colores semánticos de éxito o error.
- Mantener contraste WCAG AA: al menos 4.5:1 para texto normal y 3:1 para
  componentes gráficos y texto grande.
- Conservar los temas claro y oscuro; el modo oscuro no es una inversión
  automática del claro.
- La paleta de implementación y sus tokens viven en
  `app/static/css/estilos.css`; la especificación visual está en `DESIGN.md`.
