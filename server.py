# -*- coding: utf-8 -*-
"""
================================================================================
          ⚡ RAIAKA AUTH SERVER - SERVIDOR DE VALIDAÇÃO DE CHAVES ⚡
================================================================================
Servidor leve e independente (zero dependências externas / biblioteca padrão).
Roda localmente ou em hospedagens gratuitas (Render, PythonAnywhere, VPS).
"""

import http.server
import socketserver
import json
import time
import os
import hashlib

PORT = int(os.environ.get("PORT", 5000))
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys_database.json")

# Banco de chaves padrão inicial se não existir arquivo
DEFAULT_KEYS = {
    # Chaves Permanentes (Vitalícias)
    "SHINOBI#PERM!9xK$2026": {"type": "perm", "desc": "Vitalício", "duration": 0, "active": True, "hwid": None},
    "CPM2*LGT@VIP#77$LIF3": {"type": "perm", "desc": "Vitalício", "duration": 0, "active": True, "hwid": None},
    "ANIME$8wZ!B00ST*44#KP": {"type": "perm", "desc": "Vitalício", "duration": 0, "active": True, "hwid": None},
    "LEGIT#5yP*V00@99$M0D": {"type": "perm", "desc": "Vitalício", "duration": 0, "active": True, "hwid": None},
    "K4MI*9kL$TR41N#12!XP": {"type": "perm", "desc": "Vitalício", "duration": 0, "active": True, "hwid": None},
    
    # Chaves de Teste (20 Minutos = 1200s)
    "TEST#20M!SHIN$11@CPM": {"type": "temp", "desc": "Teste 20 Minutos", "duration": 1200, "active": True, "hwid": None},
    "20MIN*8kP@FREE#22!MOD": {"type": "temp", "desc": "Teste 20 Minutos", "duration": 1200, "active": True, "hwid": None},
    
    # Chaves Temporárias (24 Horas = 86400s)
    "DAY1#4wB!TEMP$11@24H": {"type": "temp", "desc": "Temporário (1 Dia)", "duration": 86400, "active": True, "hwid": None},
    "24HR*8kP@TEST#22!CPM": {"type": "temp", "desc": "Temporário (1 Dia)", "duration": 86400, "active": True, "hwid": None},
}

def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_KEYS.copy()

def save_db(db):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Erro ao salvar banco de dados:", e)

class RaiakaAuthHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 1. Rota de horário oficial do servidor
        if self.path == "/api/time" or self.path == "/time":
            now = time.time()
            self._send_json({"status": "ok", "server_time": now, "utc_str": time.asctime(time.gmtime(now))})
            return

        # 2. Painel Admin: Listar chaves e status de clientes
        if self.path == "/api/admin/keys" or self.path == "/admin":
            db = load_db()
            now = time.time()
            res = {}
            for k, info in db.items():
                secs_left = None
                if info.get("type") == "temp" and info.get("first_activated_at"):
                    elapsed = now - info["first_activated_at"]
                    secs_left = max(0, int(info["duration"] - elapsed))
                res[k] = {
                    "type": info.get("type"),
                    "desc": info.get("desc"),
                    "hwid": info.get("hwid"),
                    "expired": info.get("expired", False),
                    "secs_left": secs_left,
                    "first_activated_at": info.get("first_activated_at")
                }
            self._send_json({"status": "ok", "keys": res, "server_time": now})
            return

        self._send_json({"status": "error", "message": "Endpoint nao encontrado"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
        try:
            req_data = json.loads(raw_body)
        except Exception:
            self._send_json({"status": "error", "message": "JSON invalido"}, 400)
            return

        now = time.time()

        # Validação de Licença
        if self.path == "/api/validate":
            key = req_data.get("key", "").strip()
            hwid = req_data.get("hwid", "").strip()

            if not key:
                self._send_json({"valid": False, "reason": "Chave não informada!"})
                return

            db = load_db()
            if key not in db:
                self._send_json({"valid": False, "reason": "Chave de licença inválida!"})
                return

            info = db[key]
            if not info.get("active", True) or info.get("banned", False):
                self._send_json({"valid": False, "reason": "Esta chave foi desativada ou banida pelo administrador!"})
                return

            # Trava de HWID: Se a chave já pertence a outro PC, bloqueia
            bound_hwid = info.get("hwid")
            if bound_hwid and bound_hwid != hwid:
                self._send_json({"valid": False, "reason": "Esta chave já está vinculada a outro computador!"})
                return

            if not bound_hwid and hwid:
                info["hwid"] = hwid

            k_type = info.get("type", "perm")
            duration = info.get("duration", 0)

            # Chave Permanente
            if k_type == "perm":
                save_db(db)
                self._send_json({
                    "valid": True,
                    "type": "perm",
                    "desc": "Vitalício (Permanente)",
                    "server_time": now
                })
                return

            # Chave Temporária / Teste
            first_act = info.get("first_activated_at")
            if not first_act:
                first_act = now
                info["first_activated_at"] = first_act

            elapsed = now - first_act
            if elapsed >= duration or info.get("expired", False):
                info["expired"] = True
                save_db(db)
                self._send_json({
                    "valid": False,
                    "expired": True,
                    "reason": f"O período de acesso ({info.get('desc')}) expirou no servidor!"
                })
                return

            secs_left = int(duration - elapsed)
            save_db(db)
            self._send_json({
                "valid": True,
                "type": "temp",
                "desc": f"{info.get('desc')} ({secs_left//60} min restantes)",
                "secs_left": secs_left,
                "activated_at": first_act,
                "server_time": now
            })
            return

        # Revogar ou banir chave
        if self.path == "/api/admin/revoke":
            key = req_data.get("key", "").strip()
            db = load_db()
            if key in db:
                db[key]["active"] = False
                db[key]["banned"] = True
                save_db(db)
                self._send_json({"status": "ok", "message": f"Chave {key} revogada com sucesso!"})
            else:
                self._send_json({"status": "error", "message": "Chave não encontrada"}, 404)
            return

        self._send_json({"status": "error", "message": "Endpoint nao encontrado"}, 404)

if __name__ == "__main__":
    db = load_db()
    save_db(db)
    print(f"============================================================")
    print(f"[*] SERVIDOR RAIAKA AUTH ATIVO NA PORTA {PORT}")
    print(f"Horario UTC: {time.asctime(time.gmtime())}")
    print(f"Chaves carregadas: {len(db)}")
    print(f"Link local: http://localhost:{PORT}/api/time")
    print(f"Painel:     http://localhost:{PORT}/api/admin/keys")
    print(f"============================================================")
    with socketserver.TCPServer(("", PORT), RaiakaAuthHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor finalizado.")
