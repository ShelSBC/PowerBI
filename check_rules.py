import os
import json
import sys

def analizar_archivo_tmdl(file_path, file_name, rules):
    violations = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Detectar si el archivo define una Tabla
    nombre_tabla = ""
    tiene_descripcion_tabla = False
    for line in lines:
        if line.strip().startswith("table "):
            nombre_tabla = line.strip().split(" ", 1)[1].replace("'", "")
            # Verificar si las líneas anteriores tenían la descripción de la tabla
            idx = lines.index(line)
            if idx > 0 and lines[idx-1].strip().startswith("///"):
                tiene_descripcion_tabla = True
            break

    # 1. Validar Regla de Tabla en Plural y Sin Descripción
    if nombre_tabla:
        for rule in rules:
            if rule['objectType'] == 'table':
                if "!name.endsWith" in rule['condition'] and not (nombre_tabla.endswith('s') or nombre_tabla.endswith('es')):
                    violations.append((rule['name'], f"Tabla: {nombre_tabla}", "Nombre no está en plural"))
                if "description == null" in rule['condition'] and not tiene_descripcion_tabla:
                    violations.append((rule['name'], f"Tabla: {nombre_tabla}", "Falta descripción (///)"))

    # 2. Procesar Medidas y Columnas dentro del archivo
    for idx, line in enumerate(lines):
        line_clean = line.strip()
        
        # --- ANALIZAR MEDIDAS ---
        if line_clean.startswith("measure "):
            nombre_medida = line_clean.split("=", 1)[0].replace("measure ", "").strip().replace("'", "")
            
            # Recolectar bloques de información de la medida (Dax, formatString, descripción)
            expresion_completa = line_clean
            tiene_descripcion = False
            tiene_format = False
            format_value = ""
            
            # Buscar descripción hacia arriba
            if idx > 0 and lines[idx-1].strip().startswith("///"):
                tiene_descripcion = True
                
            # Buscar propiedades hacia abajo (hasta encontrar otro objeto)
            sub_idx = idx + 1
            while sub_idx < len(lines) and (lines[sub_idx].startswith("\t") or lines[sub_idx].startswith(" ")):
                sub_line = lines[sub_idx].strip()
                expresion_completa += " " + sub_line
                if sub_line.startswith("formatString:"):
                    tiene_format = True
                    format_value = sub_line.replace("formatString:", "").strip().replace("'", "").replace('"', '')
                sub_idx += 1

            # Evaluar reglas de Medidas
            for rule in rules:
                if rule['objectType'] == 'measure':
                    cond = rule['condition']
                    if "expression.includes" in cond:
                        term = cond.split("'")[1]
                        if term in expresion_completa:
                            violations.append((rule['name'], f"Medida: [{nombre_medida}]", f"Usa '{term}'"))
                    elif "description == null" in cond and not tiene_descripcion:
                        violations.append((rule['name'], f"Medida: [{nombre_medida}]", "Falta descripción (Comentario ///)"))
                    elif "formatString == null" in cond and not tiene_format:
                        violations.append((rule['name'], f"Medida: [{nombre_medida}]", "Falta formato de cadena"))

        # --- ANALIZAR COLUMNAS ---
        elif line_clean.startswith("column "):
            nombre_columna = line_clean.split(" ", 1)[1].split("=?", 1)[0].split("=", 1)[0].strip().replace("'", "")
            
            is_calculated = "=" in line_clean and "=>" not in line_clean
            is_hidden = False
            is_key = False
            data_type = ""
            format_string = ""

            # Buscar propiedades de la columna hacia abajo
            sub_idx = idx + 1
            while sub_idx < len(lines) and (lines[sub_idx].startswith("\t") or lines[sub_idx].startswith(" ")):
                sub_line = lines[sub_idx].strip()
                if sub_line == "isHidden": is_hidden = True
                if sub_line == "isKey": is_key = True
                if sub_line.startswith("dataType:"): data_type = sub_line.replace("dataType:", "").strip()
                if sub_line.startswith("formatString:"): format_string = sub_line.replace("formatString:", "").strip().replace("'", "")
                sub_idx += 1

            # Evaluar reglas de Columnas
            for rule in rules:
                if rule['objectType'] == 'column':
                    cond = rule['condition']
                    if "type == 'calculated'" in cond and is_calculated:
                        violations.append((rule['name'], f"Columna: {nombre_tabla}[{nombre_columna}]", "Es una columna calculada (Evitar)"))
                    elif "name.endsWith('ID')" in cond and (nombre_columna.endswith('ID') or nombre_columna.endswith('Key')) and not is_hidden:
                        violations.append((rule['name'], f"Columna: {nombre_tabla}[{nombre_columna}]", "Columnas ID/Key deben estar ocultas"))
                    elif "isKey == true" in cond and is_key and not is_hidden:
                        violations.append((rule['name'], f"Columna: {nombre_tabla}[{nombre_columna}]", "Llaves primarias (isKey) deben estar ocultas"))
                    elif "dataType == 'dateTime'" in cond and data_type == "dateTime" and format_string != "dd/MM/yyyy":
                        violations.append((rule['name'], f"Columna: {nombre_tabla}[{nombre_columna}]", f"Formato de fecha incorrecto ({format_string}). Debe ser dd/MM/yyyy"))

    return violations

def analizar_relaciones(file_path, rules):
    violations = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # En TMDL las relaciones suelen venir en archivos globales o bloques 'relationship'
    # Evaluamos si existen comportamientos prohibidos en el texto del archivo de relaciones
    for rule in rules:
        if rule['objectType'] == 'relationship':
            if "crossFilteringBehavior == 'bothDirections'" in rule['condition'] and "crossFilteringBehavior: bothDirections" in content:
                violations.append((rule['name'], "Relación del Modelo", "Direccionalidad Bi-direccional detectada"))
            if "fromCardinality == 'many'" in rule['condition'] and "fromCardinality: many" in content and "toCardinality: many" in content:
                # Nota: Una aproximación simple para detectar many-to-many en texto TMDL
                if "fromCardinality: many" in content and "toCardinality: many" in content:
                    violations.append((rule['name'], "Relación del Modelo", "Relación Many-to-Many detectada"))
    return violations

def run_checks():
    rules_file = 'reglas_calidad.json'
    if not os.path.exists(rules_file):
        print(f"❌ Error: No se encontró {rules_file}")
        sys.exit(1)

    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)['rules']

    total_violations = 0
    models_found = 0

    print(f"🚀 Iniciando Analizador Estructural TMDL ({len(rules)} reglas activas)...")

    for root, dirs, files in os.walk("."):
        if root.endswith(".SemanticModel"):
            models_found += 1
            path_parts = root.split(os.sep)
            dominio = path_parts[1] if len(path_parts) > 1 else "Raíz"
            reporte = os.path.basename(root).replace(".SemanticModel", "")
            
            print(f"\n📦 [{dominio.upper()} > {reporte}]")
            definition_path = os.path.join(root, "definition")
            
            if not os.path.exists(definition_path):
                continue

            for sub_root, sub_dirs, sub_files in os.walk(definition_path):
                for file in sub_files:
                    file_path = os.path.join(sub_root, file)
                    
                    if file.endswith(".tmdl"):
                        if any(x in file for x in ["LocalDateTable", "DateTableTemplate"]):
                            continue
                        
                        # Ejecutar análisis del archivo
                        errores = analizar_archivo_tmdl(file_path, file, rules)
                        errores += analizar_relaciones(file_path, rules)
                        
                        for reg, obj, desc in errores:
                            print(f"   ❌ ERROR: {reg}")
                            print(f"      🔹 Objeto: {obj}")
                            print(f"      🔹 Detalle: {desc}")
                            print(f"      🔹 Archivo: {file}\n")
                            total_violations += 1

    print("\n" + "="*50)
    print(f"📊 RESUMEN GLOBAL DE CALIDAD")
    print(f"   Modelos revisados: {models_found}")
    print(f"   Reglas rotas encontradas: {total_violations}")
    print("="*50)

    if total_violations > 0:
        print(f"\n⛔ Se encontraron {total_violations} errores estructurales. Pipeline bloqueado.")
        sys.exit(1)
    
    if models_found == 0:
        print("\n⚠️ No se detectaron modelos .SemanticModel.")
        sys.exit(0)

    print("\n✅ ¡Espectacular! Se verificaron metadatos, nombres y DAX. Cero errores.")
    sys.exit(0)

if __name__ == "__main__":
    run_checks()
