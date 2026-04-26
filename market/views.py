import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render

from btc_snapshot import fetch_ohlcv, add_indicators, build_snapshot


def index(request):
    """Render the main page with the snapshot form."""
    defaults = {
        "exchange_id": "bybit",
        "symbol":      "BTC/USDT",
        "limit":       200,
    }
    return render(request, "market/index.html", {"defaults": defaults})


@require_http_methods(["POST"])
def fetch_snapshot(request):
    """
    POST endpoint — accepts a list of timeframes, fetches data for each,
    returns a combined snapshot:
    { "symbol": "BTC/USDT", "data": { "1h": {...}, "4h": {...} } }
    """
    try:
        body        = json.loads(request.body)
        exchange_id = body.get("exchange_id", "bybit").strip()
        symbol      = body.get("symbol",      "BTC/USDT").strip().upper()
        timeframes  = body.get("timeframes",  ["15m"])
        limit       = int(body.get("limit",   200))

        if not isinstance(timeframes, list) or len(timeframes) == 0:
            return JsonResponse(
                {"error": "Выберите хотя бы один таймфрейм"},
                status=400,
            )

        if limit < 50 or limit > 1000:
            return JsonResponse(
                {"error": "limit должен быть от 50 до 1000"},
                status=400,
            )

        result_data = {}
        errors      = {}

        for tf in timeframes:
            tf = tf.strip()
            try:
                df      = fetch_ohlcv(exchange_id, symbol, tf, limit)
                df      = add_indicators(df)
                snap    = build_snapshot(df, symbol, tf)
                # убираем дублирующие поля — они уже есть на верхнем уровне
                snap.pop("symbol",    None)
                snap.pop("timeframe", None)
                result_data[tf] = snap
            except SystemExit as e:
                errors[tf] = str(e)
            except Exception as e:
                errors[tf] = str(e)

        if not result_data:
            return JsonResponse(
                {"error": "Не удалось получить данные ни для одного таймфрейма", "details": errors},
                status=502,
            )

        response = {"symbol": symbol, "data": result_data}
        if errors:
            response["errors"] = errors

        return JsonResponse(response, json_dumps_params={"ensure_ascii": False})

    except (ValueError, KeyError) as e:
        return JsonResponse({"error": f"Неверные параметры: {e}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
