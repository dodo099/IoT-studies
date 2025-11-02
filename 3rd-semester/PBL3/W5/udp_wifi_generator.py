#!/usr/bin/env python3
"""
udp_wifi_generator.py - prosty UDP "generator" (RPi lub inny Linux)

Funkcje:
 - continuous: ciągłe wysyłanie (interval = sekundy między pakietami; 0 => maksymalna prędkość)
 - intermittent: okresowy cykl (period, on_duration), w czasie ON wysyła co send_interval
 - single: wyślij jeden pakiet i zakończ
 - manual: nic nie wysyła automatycznie, pakiet tylko po naciśnięciu Enter
 - w dowolnym trybie: naciśnij Enter, aby wysłać pojedynczy pakiet natychmiast
"""

import socket
import argparse
import threading
import time
import sys
import signal

def sender_loop(sock, dest, payload, stop_evt, mode, interval, period, on_duration, send_interval):
    """Główny pętlowy nadawacz."""
    payload_b = payload if isinstance(payload, bytes) else payload.encode()
    try:
        while not stop_evt.is_set():
            if mode == "continuous":
                try:
                    sock.sendto(payload_b, dest)
                except Exception as e:
                    print("[ERROR] send:", e)
                if interval > 0:
                    stop_evt.wait(interval)
                else:
                    time.sleep(0.001)
            elif mode == "intermittent":
                t_end = time.time() + on_duration
                while time.time() < t_end and not stop_evt.is_set():
                    try:
                        sock.sendto(payload_b, dest)
                    except Exception as e:
                        print("[ERROR] send:", e)
                    if send_interval > 0:
                        stop_evt.wait(send_interval)
                    else:
                        time.sleep(0.001)
                rem = period - on_duration
                if rem > 0:
                    stop_evt.wait(rem)
            elif mode == "manual":
                # w trybie manualnym nic nie wysyła automatycznie
                time.sleep(0.2)
            else:
                time.sleep(0.1)
    except Exception as e:
        print("[ERROR] sender_loop:", e)

def input_thread_func(sock, dest, payload, stop_evt):
    """Wątek nasłuchujący Enter — po naciśnięciu wysyła pojedynczy pakiet."""
    payload_b = payload if isinstance(payload, bytes) else payload.encode()
    print("Naciśnij Enter, aby wysłać pakiet. Ctrl+C aby zakończyć.")
    try:
        while not stop_evt.is_set():
            line = sys.stdin.readline()
            if line == "" and stop_evt.is_set():
                break
            try:
                sock.sendto(payload_b, dest)
                print("[SENT] manual")
            except Exception as e:
                print("[ERROR] manual send:", e)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Prosty UDP generator (continuous/intermittent/single/manual) + Enter->single")
    parser.add_argument("--dst", "-d", default="127.0.0.1", help="Adres docelowy (domyślnie 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=9000, help="Port docelowy (domyślnie 9000)")
    parser.add_argument("--payload", default="Hello", help="Tekst payload (domyślnie 'Hello')")
    parser.add_argument("--mode", choices=["continuous","intermittent","single","manual"], default="single", help="Tryb pracy")
    parser.add_argument("--interval", type=float, default=0.1, help="Interwał między pakietami w continuous (s); 0 = max")
    parser.add_argument("--period", type=float, default=5.0, help="Pełen okres dla intermittent (s)")
    parser.add_argument("--on", dest="on_duration", type=float, default=1.0, help="Czas ON w intermittent (s)")
    parser.add_argument("--send-interval", type=float, default=0.05, help="Interwał między pakietami podczas ON w intermittent (s); 0 = max")
    parser.add_argument("--broadcast", action="store_true", help="Włącz broadcast socket option")
    args = parser.parse_args()

    dest = (args.dst, args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if args.broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    stop_evt = threading.Event()
    def handle_sigint(signum, frame):
        stop_evt.set()
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    if args.mode == "single":
        sock.sendto(args.payload.encode(), dest)
        print(f"[SENT] single -> {args.dst}:{args.port}")
        return

    t = threading.Thread(target=sender_loop, args=(sock,dest,args.payload,stop_evt,args.mode,args.interval,args.period,args.on_duration,args.send_interval), daemon=True)
    t.start()
    tin = threading.Thread(target=input_thread_func, args=(sock,dest,args.payload,stop_evt), daemon=True)
    tin.start()

    print(f"[START] mode={args.mode}, dst={args.dst}:{args.port}, payload={args.payload!r}")
    try:
        while not stop_evt.is_set():
            time.sleep(0.2)
    finally:
        stop_evt.set()
        t.join(timeout=1)
        tin.join(timeout=1)
        sock.close()
        print("[EXIT] Zakończono.")

if __name__ == "__main__":
    main()
