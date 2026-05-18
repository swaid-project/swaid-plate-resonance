#!/usr/bin/env python3
"""
Teste Direto de LEDs via Serial (Pico)
========================================
Envia comandos FX:<num> diretamente para o Pico via USB Serial.
Não usa ZeroMQ — comunica diretamente com a porta serial do Pico.

Instalar dependências:
    python -m pip install pyserial

Uso:
    python3 test_pico_led.py

Comandos no menu:
    <número>    → Envia FX:<número> (ex: 5, 10, 17)
    r           → Envia FX com efeito aleatório
    s           → Mostra lista de efeitos
    q           → Sair
"""

import serial
import serial.tools.list_ports
import random
import time
import sys

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


def encontrar_porta_pico():
    portas = serial.tools.list_ports.comports()
    for p in portas:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(x in desc or x in hwid for x in ["pico", "rp2040", "rp2350", "2e8a"]):
            return p.device
    print("Pico não detetado automaticamente. Portas disponíveis:")
    for p in portas:
        print(f"  {p.device} — {p.description}")
    return input("Escreve a porta manualmente (ex: /dev/ttyACM0): ").strip()


def enviar_fx(ser, fx_id):
    cmd = f"FX:{fx_id}\n"
    try:
        ser.write(cmd.encode())
        print(f"→ Enviado: FX:{fx_id} — {NOMES_EFEITOS[fx_id]}")
    except Exception as e:
        print(f"[Erro] Falha ao enviar: {e}")


def print_menu():
    print("\n===== Teste Direto Pico LEDs =====")
    print("<número>  → Envia FX:<número> (0–19)")
    print("r         → Efeito aleatório")
    print("s         → Mostrar lista de efeitos")
    print("q         → Sair")


def main():
    porta = encontrar_porta_pico()
    print(f"A ligar ao Pico em {porta}...")

    try:
        ser = serial.Serial(porta, 9600, timeout=1)
        time.sleep(2)
        print("✅ Ligado!\n")
    except Exception as e:
        print(f"❌ Erro ao ligar: {e}")
        sys.exit(1)

    try:
        while True:
            print_menu()
            escolha = input("Escolha: ").strip().lower()

            if escolha == "q":
                print("A sair...")
                break
            elif escolha == "r":
                fx = random.randint(0, TOTAL_EFEITOS - 1)
                enviar_fx(ser, fx)
            elif escolha == "s":
                print("\nEfeitos disponíveis:")
                for nome in NOMES_EFEITOS:
                    print(f"  {nome}")
            else:
                try:
                    fx = int(escolha)
                    if 0 <= fx < TOTAL_EFEITOS:
                        enviar_fx(ser, fx)
                    else:
                        print(f"[Erro] ID deve estar entre 0 e {TOTAL_EFEITOS - 1}")
                except ValueError:
                    print("[Erro] Escolha inválida.")

    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        ser.close()
        print("Serial encerrado.")


if __name__ == "__main__":
    raise SystemExit(main())
