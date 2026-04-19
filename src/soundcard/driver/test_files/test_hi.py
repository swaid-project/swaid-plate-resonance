import argparse
import ctypes
import os
import random
import sys
import time

SYMBOLS = [
    "CHLADNI_CROSS",
    "CHLADNI_STAR_4",
    "CHLADNI_RING",
    "CHLADNI_DIAGONAL",
    "CHLADNI_GRID_2x2",
    "CHLADNI_STAR_8",
    "CHLADNI_SPIRAL",
    "CHLADNI_FLOWER_6",
    "CHLADNI_BUTTERFLY",
    "CHLADNI_MANDALA",
    "CHLADNI_TORUS_KNOT",
]
LEDS = ["PULSE_R", "PULSE_G", "PULSE_B", "SOLID_WHITE", "STROBE_R"]
TRANSITIONS = ["LOW", "MEDIUM", "HIGH"]


def load_library() -> ctypes.CDLL:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(base_dir, "trans.so")

    if not os.path.exists(lib_path):
        print(f"Erro: Biblioteca {lib_path} nao encontrada. Corre 'make {lib_path}'.")
        sys.exit(1)

    trans_lib = ctypes.CDLL(lib_path)
    trans_lib.send_trigger.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_float]
    trans_lib.send_trigger.restype = ctypes.c_int

    trans_lib.init_zmq.argtypes = [ctypes.c_char_p]
    trans_lib.init_zmq.restype = None

    trans_lib.cleanup_zmq.argtypes = []
    trans_lib.cleanup_zmq.restype = None
    return trans_lib


def send_packet(trans_lib: ctypes.CDLL, symbol: str, led: str, transition: str, volume: float) -> None:
    result = trans_lib.send_trigger(
        symbol.encode("utf-8"),
        led.encode("utf-8"),
        transition.encode("utf-8"),
        ctypes.c_float(volume),
    )

    if result == 1:
        print(f"[Enviado] Symbol: {symbol:<20} | LED: {led:<10} | Transition: {transition:<6} | Vol: {volume:5.1f}%")
    elif result == 0:
        print("[Aviso] Fila ZeroMQ cheia. Pacote descartado (DONTWAIT).")
    else:
        print("[Erro] Falha no envio via ZeroMQ.")


def random_payload() -> tuple[str, str, str, float]:
    return (
        random.choice(SYMBOLS),
        random.choice(LEDS),
        random.choice(TRANSITIONS),
        random.uniform(0.0, 100.0),
    )


def ask_manual_payload() -> tuple[str, str, str, float]:
    print("\nManual packet (carrega Enter para usar default):")
    symbol = input(f"  symbol [{SYMBOLS[0]}]: ").strip() or SYMBOLS[0]
    led = input(f"  led [{LEDS[0]}]: ").strip() or LEDS[0]
    transition = input(f"  transition [{TRANSITIONS[1]}]: ").strip() or TRANSITIONS[1]

    while True:
        raw_volume = input("  volume [0-100, default 50]: ").strip()
        if not raw_volume:
            volume = 50.0
            break
        try:
            volume = float(raw_volume)
            if 0.0 <= volume <= 100.0:
                break
            print("  Valor fora do intervalo [0,100].")
        except ValueError:
            print("  Valor invalido.")

    return symbol, led, transition, volume


def print_menu() -> None:
    print("\n===== HI Sender Menu =====")
    print("1) Enviar pacote manual")
    print("2) Enviar 1 pacote random")
    print("3) Enviar N pacotes random")
    print("4) Mostrar listas disponiveis")
    print("q) Sair")


def send_random_batch(trans_lib: ctypes.CDLL) -> None:
    try:
        count = int(input("Numero de pacotes: ").strip())
    except ValueError:
        print("Numero invalido.")
        return

    try:
        min_delay = float(input("Delay minimo (s) [default 0.2]: ").strip() or "0.2")
        max_delay = float(input("Delay maximo (s) [default 1.0]: ").strip() or "1.0")
    except ValueError:
        print("Delay invalido.")
        return

    if count <= 0 or min_delay < 0 or max_delay < min_delay:
        print("Parametros invalidos.")
        return

    for i in range(count):
        send_packet(trans_lib, *random_payload())
        if i < count - 1:
            time.sleep(random.uniform(min_delay, max_delay))


def main() -> int:
    parser = argparse.ArgumentParser(description="HI sender for ZeroMQ trigger packets")
    parser.add_argument("--socket", default="ipc:///tmp/swaid.sock", help="ZeroMQ socket endpoint")
    args = parser.parse_args()

    trans_lib = load_library()
    trans_lib.init_zmq(args.socket.encode("utf-8"))
    print(f"[HI Subsystem] ZeroMQ inicializado em {args.socket}")

    try:
        while True:
            print_menu()
            choice = input("Escolha: ").strip().lower()

            if choice == "1":
                send_packet(trans_lib, *ask_manual_payload())
            elif choice == "2":
                send_packet(trans_lib, *random_payload())
            elif choice == "3":
                send_random_batch(trans_lib)
            elif choice == "4":
                print(f"Symbols: {', '.join(SYMBOLS)}")
                print(f"LEDs: {', '.join(LEDS)}")
                print(f"Transitions: {', '.join(TRANSITIONS)}")
            elif choice == "q":
                break
            else:
                print("Opcao invalida.")
    except KeyboardInterrupt:
        print("\n[HI Subsystem] Interrompido pelo utilizador.")
    finally:
        trans_lib.cleanup_zmq()
        print("[HI Subsystem] ZeroMQ encerrado de forma segura.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())