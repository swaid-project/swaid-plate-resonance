"""
Controlador de LEDs via Teclado
================================
DEPRECATED: LED control is now handled automatically by rx_driver.cpp
via ZeroMQ triggers. This keyboard controller is kept for debugging only.

Seta Direita  → avança efeito  (envia 'R' ao Pico)
Seta Esquerda → recua efeito   (envia 'L' ao Pico)
Q             → sair

Instalar dependências:
    python -m pip install pyserial pynput
"""

import serial
import serial.tools.list_ports
import threading
import random
import time
from pynput import keyboard

TOTAL_EFEITOS = 20
NOMES_EFEITOS = [
    "0  — Arco-Íris Fluido",
    "1  — Confetes",
    "2  — Scanner Cylon",
    "3  — Respiração Oceano",
    "4  — Aurora Boreal",
    "5  — Cometa Arco-Íris",
    "6  — Plasma Quântico",
    "7  — Scanner Duplo",
    "8  — Vagalumes",
    "9  — Serpente Cromática",
    "10 — Explosão de Estrela",
    "11 — Preenchimento Surpresa",
    "12 — 🔥 Fogo",
    "13 — 🌊 Água",
    "14 — 💚 Matrix",
    "15 — 🌋 Lava",
    "16 — ⚡ Tempestade",
    "17 — 🌌 Galáxia",
    "18 — 💜 Néon",
    "19 — ❄️  Neveiro",
]

efeito_atual = 0
ser = None
a_correr = True

# ── Deteção automática da porta ───────────────────────────────────────────
def encontrar_porta_pico():
    portas = serial.tools.list_ports.comports()
    for p in portas:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(x in desc or x in hwid for x in ["pico", "rp2040", "2e8a"]):
            return p.device
    # Fallback: lista portas e pede ao utilizador
    print("Pico não detetado automaticamente. Portas disponíveis:")
    for p in portas:
        print(f"  {p.device} — {p.description}")
    return input("Escreve a porta manualmente (ex: COM3): ").strip()

# ── Handshake ─────────────────────────────────────────────────────────────
def fazer_handshake():
    seq = random.randint(1, 9999)
    msg = f"INT:{seq}\n"
    print(f"A fazer handshake (seq={seq})...")
    ser.write(msg.encode())
    timeout = time.time() + 3  # espera até 3 segundos
    while time.time() < timeout:
        if ser.in_waiting:
            resp = ser.readline().decode().strip()
            if resp == f"received:{seq}":
                print(f"✅ Handshake confirmado pelo Pico!\n")
                return True
    print("⚠️  Sem resposta ao handshake — continua na mesma.")
    return False

# ── Thread: lê mensagens do Pico em background ───────────────────────────
def ler_serial():
    global a_correr
    while a_correr:
        try:
            if ser and ser.in_waiting:
                linha = ser.readline().decode().strip()
                if linha.startswith("alive:"):
                    pass  # ping silencioso — Pico está vivo
                elif linha.startswith("ok:"):
                    partes = linha.split(":")
                    # ok:R:5  ou  ok:L:3
                    print(f"  ✔ Confirmado pelo Pico → efeito {partes[2]} ({NOMES_EFEITOS[int(partes[2])]})")
                elif linha == "PONG":
                    pass  # resposta ao ping do PC
                elif linha:
                    print(f"  [Pico] {linha}")
        except Exception:
            pass
        time.sleep(0.05)

# ── Enviar comando ────────────────────────────────────────────────────────
def enviar_comando(cmd):
    global efeito_atual
    try:
        ser.write((cmd + "\n").encode())
        if cmd == 'R':
            efeito_atual = (efeito_atual + 1) % TOTAL_EFEITOS
            print(f"\n→ Enviado: DIREITA | A aguardar confirmação...")
        elif cmd == 'L':
            efeito_atual = (efeito_atual - 1) % TOTAL_EFEITOS
            print(f"\n← Enviado: ESQUERDA | A aguardar confirmação...")
    except Exception as e:
        print(f"Erro ao enviar: {e}")

# ── Listener de teclado ───────────────────────────────────────────────────
def ao_pressionar(tecla):
    global a_correr
    try:
        if tecla == keyboard.Key.right:
            enviar_comando('R')
        elif tecla == keyboard.Key.left:
            enviar_comando('L')
        elif hasattr(tecla, 'char') and tecla.char in ('q', 'Q'):
            print("\nA sair...")
            a_correr = False
            ser.close()
            return False
    except Exception:
        pass

# ── MAIN ──────────────────────────────────────────────────────────────────
porta = encontrar_porta_pico()
print(f"A ligar ao Pico em {porta}...")

try:
    ser = serial.Serial(porta, 9600, timeout=1)
    time.sleep(2)  # espera o Pico arrancar
    print("✅ Ligado!\n")
except Exception as e:
    print(f"❌ Erro ao ligar: {e}")
    exit(1)

fazer_handshake()

# Inicia thread de leitura em background
t = threading.Thread(target=ler_serial, daemon=True)
t.start()

print(f"Efeito inicial: {NOMES_EFEITOS[efeito_atual]}")
print("Usa ← → para mudar efeitos. Q para sair.\n")

with keyboard.Listener(on_press=ao_pressionar) as listener:
    listener.join()
