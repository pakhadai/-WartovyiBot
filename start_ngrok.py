from pyngrok import ngrok


def start_ngrok():
    # Запускаємо ngrok на порті 8000
    http_tunnel = ngrok.connect(8000, "http")
    print("Ngrok URL:", http_tunnel.public_url)
    print("Натисни Ctrl+C щоб зупинити ngrok")

    try:
        # Тримати тунель відкритим
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Зупинка ngrok...")
        ngrok.disconnect(http_tunnel.public_url)
        ngrok.kill()


if __name__ == "__main__":
    start_ngrok()
