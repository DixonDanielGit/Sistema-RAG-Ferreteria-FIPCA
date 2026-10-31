// Objeto con las expresiones regulares y mensajes de validación para cada tipo de campo
export const expresiones = {
    nombre: {
        expresion: /^[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ]{1,}(\s[A-ZÁÉÍÓÚÑa-záéíóúñ]{1,})*$/,
        mensajeError:
            "El nombre debe iniciar con mayúscula y tener al menos 2 letras por palabra.",
    },
    apellido: {
        expresion: /^[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ]{1,}(\s[A-ZÁÉÍÓÚÑa-záéíóúñ]{1,})*$/,
        mensajeError:
            "El apellido debe iniciar con mayúscula y contener solo letras.",
    },
    usuario: {
        expresion: /^[a-zA-Z0-9][a-zA-Z0-9._-]{2,48}[a-zA-Z0-9]$/,
        mensajeError:
            "El usuario debe tener entre 4 y 50 caracteres (letras, números, puntos o guiones).",
    },
    correo: {
        expresion: /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/,
        mensajeError:
            "El correo debe tener un formato válido (ej: usuario@dominio.com).",
    },
    password: {
        expresion: /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/,
        mensajeError:
            "La contraseña debe tener al menos 8 caracteres y combinar letras y números.",
    },
    passwordNew: {
        expresion: /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/,
        mensajeError:
            "La contraseña debe tener al menos 8 caracteres y combinar letras y números.",
    },
    passwordConf: {
        expresion: /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/,
        mensajeError:
            "Las contraseñas no coinciden o no cumplen con el formato requerido.",
    },
    cedula: {
        expresion: /^([VEJPGvejpg]-?)?[0-9]{6,9}$/,
        mensajeError:
            "La cédula debe contener entre 6 y 9 dígitos numéricos (ej: 12345678 o V-12345678).",
    },
    rol: {
        expresion: /^[a-z][a-z0-9_-]{1,49}$/,
        mensajeError: "Por favor, seleccione un rol válido.",
    },
    categoria: {
        expresion: /^[A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]{2,49}$/,
        mensajeError:
            "La categoría debe iniciar con mayúscula, contener al menos 3 letras y solo puede incluir letras y espacios.",
    },
    codigo: {
        expresion: /^\d{6,11}$/,
        mensajeError:
            "El código debe contener solo números y tener al menos 6 caracteres.",
    },
    telefono: {
        expresion: /^(0?)(412|414|416|424|426|422|212|24[1-9]|25[1-9])\d{7}$/,
        mensajeError:
            'El teléfono debe comenzar con código de área válido (ej: 0412, 0414, 0424, 0212) seguido de 7 dígitos.',
    },
    direccion: {
        expresion: /^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s.,#\-°]{10,150}$/,
        mensajeError: "La dirección debe tener entre 10 y 150 caracteres.",
    },
    descripcion: {
        expresion: /^([A-ZÁÉÍÓÚÑ][a-záéíóúñ0-9\s.,#-]{8,})$/,
        mensajeError: "La descripción debe comenzar con mayúscula y tener al menos 9 caracteres.",
    },
    cantidad: {
        expresion: /^([1-9]{1})([0-9]{0,3})?$/,
        mensajeError: "La cantidad debe ser un número entre 1 y 9999.",
    },
    precio: {
        expresion: /^(?!(0|0[.,]0*)$)\d+([.,]\d{1,2})?$/,
        mensajeError: "El precio debe ser un número válido mayor a 0 (ej: 10.50).",
    },
    marca: {
        expresion: /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]{3,20}$/,
        mensajeError: "La marca debe iniciar con mayúscula y tener al menos 4 caracteres.",
    },
    medida: {
        expresion: /^\d+(\.\d+)?\s?(ml|L|g|kg|m|cm|mm|pulg|unid)$/,
        mensajeError: "La unidad de medida no es válida.",
    },
    id_personal: {
        expresion: /^[a-zA-Z0-9]{10,}$/,
        mensajeError: "Identificador inválido.",
    },
    fn: {
        expresion: /^\d{4}-\d{2}-\d{2}$/,
        mensajeError: "Fecha inválida (formato requerido: AAAA-MM-DD).",
    },
    fechaDeCita: {
        expresion: /^\d{4}-\d{2}-\d{2}$/,
        mensajeError: "Fecha inválida (formato requerido: AAAA-MM-DD).",
    },
};

/**
 * Obtiene los elementos auxiliares de validación vinculados al campo (icono check, icono error, mensaje).
 */
export function obtenerElementosCampo(input) {
    const campoCustom = input.closest(".campo-custom") || input.parentElement;
    if (!campoCustom) return null;

    const pError =
        campoCustom.querySelector(".p-error-validaciones") ||
        campoCustom.querySelector("p");
    const check = campoCustom.querySelector(".check");
    const error = campoCustom.querySelector(".error");

    return {
        campoCustom: campoCustom,
        pError: pError,
        check: check,
        error: error,
    };
}

/**
 * Actualiza la visibilidad de los iconos de confirmación y error.
 */
export function chulitoYX(check, error, estado) {
    if (!check || !error) return;

    if (estado === "valido") {
        check.classList.remove("d-none");
        error.classList.add("d-none");
    } else if (estado === "inValido") {
        check.classList.add("d-none");
        error.classList.remove("d-none");
    } else if (estado === "vacio") {
        check.classList.add("d-none");
        error.classList.add("d-none");
    }
}

/**
 * Actualiza el aspecto visual (clases valido / invalido) en el input y sus contenedores.
 */
export function actualizarEstadoInput(input, estado) {
    const esCorrecto = estado === "correcto";
    const esIncorrecto = estado === "incorrecto";

    input.classList.toggle("valido", esCorrecto);
    input.classList.toggle("invalido", esIncorrecto);

    if (input.parentElement) {
        input.parentElement.classList.toggle("valido", esCorrecto);
        input.parentElement.classList.toggle("invalido", esIncorrecto);
    }

    const campoCustom = input.closest(".campo-custom");
    if (campoCustom && campoCustom !== input.parentElement) {
        campoCustom.classList.toggle("valido", esCorrecto);
        campoCustom.classList.toggle("invalido", esIncorrecto);
    }
}

/**
 * Valida un campo de tipo <select>.
 */
export function validarSelect(select, elementos, campos, formulario, attExpresion) {
    const { pError, check, error } = elementos;
    const valor = select.value ? select.value.trim() : "";
    const regDef = expresiones[attExpresion];

    const esInvalido =
        valor === "" ||
        valor === "selection" ||
        (regDef && !regDef.expresion.test(valor));

    if (esInvalido) {
        if (pError) {
            pError.textContent =
                regDef && regDef.mensajeError
                    ? regDef.mensajeError
                    : "Por favor, seleccione una opción válida.";
            pError.classList.remove("d-none");
        }
        chulitoYX(check, error, "inValido");
        actualizarEstadoInput(select, "incorrecto");
        if (campos) campos[select.name] = false;
        return false;
    } else {
        if (pError) {
            pError.textContent = "";
            pError.classList.add("d-none");
        }
        chulitoYX(check, error, "valido");
        actualizarEstadoInput(select, "correcto");
        if (campos) campos[select.name] = true;
        return true;
    }
}

/**
 * Valida un campo individual (input text, password, email, etc.).
 */
export function validarCampo(
    expresion,
    input,
    campo,
    campos,
    formulario,
    elementos,
    mensajeError,
    valorAValidar
) {
    const { pError, check, error } = elementos;
    const valor = (valorAValidar !== undefined ? valorAValidar : input.value || "").trim();

    // Caso especial: Confirmación de contraseña
    if (campo === "passwordConf") {
        const inputPassword = formulario ? formulario.elements["password"] : null;
        const valorPassword = inputPassword ? inputPassword.value : "";

        if (valor === "") {
            if (!input.required) {
                if (pError) {
                    pError.textContent = "";
                    pError.classList.add("d-none");
                }
                actualizarEstadoInput(input, "limpio");
                chulitoYX(check, error, "vacio");
                if (campos) campos[campo] = true;
                return true;
            }

            if (pError) {
                pError.textContent = "Por favor confirme la contraseña.";
                pError.classList.remove("d-none");
            }
            actualizarEstadoInput(input, "incorrecto");
            chulitoYX(check, error, "inValido");
            if (campos) campos[campo] = false;
            return false;
        }

        if (valor !== valorPassword) {
            if (pError) {
                pError.textContent = "Las contraseñas no coinciden.";
                pError.classList.remove("d-none");
            }
            actualizarEstadoInput(input, "incorrecto");
            chulitoYX(check, error, "inValido");
            if (campos) campos[campo] = false;
            return false;
        }

        if (expresion && !expresion.test(valor)) {
            if (pError) {
                pError.textContent = mensajeError;
                pError.classList.remove("d-none");
            }
            actualizarEstadoInput(input, "incorrecto");
            chulitoYX(check, error, "inValido");
            if (campos) campos[campo] = false;
            return false;
        }

        // Si coincide y cumple formato
        if (pError) {
            pError.textContent = "";
            pError.classList.add("d-none");
        }
        actualizarEstadoInput(input, "correcto");
        chulitoYX(check, error, "valido");
        if (campos) campos[campo] = true;
        return true;
    }

    // Si el campo está vacío
    if (valor === "") {
        if (input.required) {
            if (pError) {
                pError.textContent = "Este campo es obligatorio.";
                pError.classList.remove("d-none");
            }
            actualizarEstadoInput(input, "incorrecto");
            chulitoYX(check, error, "inValido");
            if (campos) campos[campo] = false;
            return false;
        } else {
            // Campo opcional vacío: estado limpio
            if (pError) {
                pError.textContent = "";
                pError.classList.add("d-none");
            }
            actualizarEstadoInput(input, "limpio");
            chulitoYX(check, error, "vacio");
            if (campos) campos[campo] = true;
            return true;
        }
    }

    // Verificación contra la expresión regular
    if (expresion && expresion.test(valor)) {
        actualizarEstadoInput(input, "correcto");
        if (pError) {
            pError.textContent = "";
            pError.classList.add("d-none");
        }
        chulitoYX(check, error, "valido");
        if (campos) campos[campo] = true;

        // Si modificó 'password' y existe 'passwordConf' con datos, revalidar confirmación
        if (campo === "password" && formulario && formulario.elements["passwordConf"]) {
            const confInput = formulario.elements["passwordConf"];
            if (confInput.value) {
                validarUnInput(confInput, formulario, campos);
            }
        }
        return true;
    } else {
        actualizarEstadoInput(input, "incorrecto");
        if (pError) {
            pError.textContent = mensajeError;
            pError.classList.remove("d-none");
        }
        chulitoYX(check, error, "inValido");
        if (campos) campos[campo] = false;
        return false;
    }
}

/**
 * Valida un input específico del formulario.
 */
export function validarUnInput(input, formulario, campos) {
    const nombreCampo = input.name;
    if (!nombreCampo) return true;

    const elementos = obtenerElementosCampo(input);
    if (!elementos) return true;

    if (input.tagName === "SELECT") {
        return validarSelect(input, elementos, campos, formulario, nombreCampo);
    }

    const regDef = expresiones[nombreCampo];
    if (!regDef) {
        // Si no tiene expresión específica pero es required y está vacío
        if (input.required && !input.value.trim()) {
            if (elementos.pError) {
                elementos.pError.textContent = "Este campo es obligatorio.";
                elementos.pError.classList.remove("d-none");
            }
            actualizarEstadoInput(input, "incorrecto");
            chulitoYX(elementos.check, elementos.error, "inValido");
            if (campos) campos[nombreCampo] = false;
            return false;
        }
        return true;
    }

    return validarCampo(
        regDef.expresion,
        input,
        nombreCampo,
        campos,
        formulario,
        elementos,
        regDef.mensajeError
    );
}

/**
 * Restablece las clases y mensajes de validación de un formulario a su estado inicial.
 */
export function limpiarValidacionFormulario(formulario, campos) {
    if (!formulario) return;
    const inputs = formulario.querySelectorAll(".input-validar");

    inputs.forEach((input) => {
        input.classList.remove("valido", "invalido");
        if (input.parentElement) {
            input.parentElement.classList.remove("valido", "invalido");
        }

        const elementos = obtenerElementosCampo(input);
        if (elementos) {
            if (elementos.campoCustom) {
                elementos.campoCustom.classList.remove("valido", "invalido");
            }
            if (elementos.pError) {
                elementos.pError.classList.add("d-none");
                elementos.pError.textContent = "";
            }
            chulitoYX(elementos.check, elementos.error, "vacio");
        }

        if (campos && input.name) {
            campos[input.name] = false;
        }
    });
}

/**
 * Inicializa la validación en vivo para un formulario con inputs con clase .input-validar.
 * Devuelve un controlador con métodos para verificar y limpiar el formulario.
 */
export function inicializarValidacionFormulario(formulario) {
    if (!formulario) return null;
    const campos = {};
    const inputs = formulario.querySelectorAll(".input-validar");

    inputs.forEach((input) => {
        if (input.name) {
            campos[input.name] = false;
        }

        const manejadorEvento = () => {
            validarUnInput(input, formulario, campos);
        };

        input.addEventListener("input", manejadorEvento);
        input.addEventListener("keyup", manejadorEvento);
        input.addEventListener("blur", manejadorEvento);

        if (input.tagName === "SELECT") {
            input.addEventListener("change", manejadorEvento);
        }
    });

    // Función verificadora completa (ejecutada antes de submit)
    const verificar = function verificarFormulario() {
        let todosValidos = true;
        inputs.forEach((input) => {
            const esValido = validarUnInput(input, formulario, campos);
            if (!esValido) {
                todosValidos = false;
            }
        });
        return todosValidos;
    };

    // Propiedades adicionales en el objeto retornado
    verificar.verificar = verificar;
    verificar.limpiar = function () {
        limpiarValidacionFormulario(formulario, campos);
    };
    verificar.campos = campos;

    return verificar;
}

// Compatibilidad con scripts no modulares
if (typeof window !== "undefined") {
    window.FipcaValidaciones = {
        expresiones,
        inicializarValidacionFormulario,
        limpiarValidacionFormulario,
        validarUnInput,
        validarCampo,
        validarSelect,
        chulitoYX,
    };
}
