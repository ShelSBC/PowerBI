import os
import json
import sys

def run_checks():
    rules_file = 'reglas_calidad.json'
    
    # 1. Validación de existencia del archivo de reglas
    if not os.path.exists(rules_file):
        print(f"❌ Error: No se encontró {rules_file}")
        sys.exit(1)

    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)['rules']

    total_violations = 0
    models_found = 0

    print("🚀 Iniciando Escaneo Estricto de Calidad Power BI...")

    # 2. Buscamos modelos en toda la estructura de carpetas
    for root, dirs, files in os.walk("."):
        if root.endswith(".SemanticModel"):
            models_found += 1
            print(f"\n📂 Analizando: {root}")
            
            definition_path = os.path.join(root, "definition")
            if not os.path.exists(definition_path):
                continue

            # 3. Escaneo de archivos TMDL
            for sub_root, sub_dirs, sub_files in os.walk(definition_path):
                for file in sub_files:
                    if file.endswith(".tmdl"):
                        # Ignorar tablas automáticas
                        if any(x in file for x in ["LocalDateTable", "DateTableTemplate"]):
                            continue
                        
                        file_path = os.path.join(sub_root, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 4. Verificación de Reglas
                        for rule in rules:
                            condition = rule.get('condition', '')
                            if "expression.includes" in condition:
                                search_term = condition.split("'")[1]
                                
                                if search_term in content:
                                    # IMPORTANTE: Aquí imprimimos todo como ERROR 
                                    # para que sepas qué regla se rompió.
                                    print(f"   ❌ REGLA ROTA: {rule['name']} en el archivo [{file}]")
                                    total_violations += 1

    # 5. Lógica de Salida Final
    print("\n" + "="*50)
    print(f"📊 RESULTADO FINAL")
    print(f"   Modelos revisados: {models_found}")
    print(f"   Reglas rotas:      {total_violations}")
    print("="*50)

    if total_violations > 0:
        print(f"\n⛔ Se encontraron {total_violations} violaciones de calidad.")
        print("El pipeline se detendrá y se enviará una notificación por correo.")
        sys.exit(1) # Código 1 = Error en GitHub Actions (Dispara el correo)
    
    if models_found == 0:
        print("\n⚠️ No se encontraron modelos para revisar.")
        sys.exit(0)

    print("\n✅ ¡Excelente! Todos los reportes cumplen con los estándares.")
    sys.exit(0)

if __name__ == "__main__":
    run_checks()
