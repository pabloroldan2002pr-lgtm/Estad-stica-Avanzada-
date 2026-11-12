#!/usr/bin/env python3
"""
Actualiza la web de Estadística Avanzada de la Segunda FEB.

Fuentes, en este orden:
  1. BueStats (buestats2.com): calendario de cada grupo y totales de equipo de cada partido.
  2. Actas oficiales de la FEB (baloncestoenvivo.feb.es): para los partidos ya jugados
     que BueStats todavía no tiene.
  3. Copa España (FEB): partidos de los equipos del Grupo A, para las pestañas «+ Copa».

Genera data.json e index.html (a partir de plantilla.html). Solo usa la librería estándar.
"""
import datetime as dt
import html as htmllib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------- ajustes de temporada
TEMPORADA = 2026                       # 2026 = temporada 2026/27
BUESTATS_API = "https://061eg05vof.execute-api.us-east-1.amazonaws.com/prod/api/v1/competition/"
BUESTATS_LIGAS = {"A": 21, "B": 20}    # En BueStats: «Liga LEB Plata» Oeste = Grupo A, Este = Grupo B
FEB = "https://baloncestoenvivo.feb.es"
COPA_URL = FEB + "/resultados/copaespaa/73/2026"   # Copa España 2026/27
ALIAS = {"BCBADAJOZ": "IREN BCBADAJOZ", "LA SALUD CARTAGENA C.B.": "BASKET CARTAGENA"}
MADRID = ZoneInfo("Europe/Madrid")
MARGEN_HORAS = 3                       # un partido se busca en la FEB pasadas 3 h de su hora

AQUI = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (X11; Linux x86_64) EstadisticaAvanzada/1.0"

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def log(*a):
    print(*a, flush=True)


def get(url, data=None, intentos=3, json_=False):
    """Descarga una URL (GET, o POST si hay data). Reintenta ante errores de red."""
    for k in range(intentos):
        try:
            body = urllib.parse.urlencode(data).encode() if data is not None else None
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": UA,
                "Accept": "application/json" if json_ else "text/html,*/*",
                "Accept-Language": "es-ES,es;q=0.9",
            })
            with _opener.open(req, timeout=40) as r:
                txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if json_ else txt
        except urllib.error.HTTPError as e:
            if e.code == 404 and json_:
                try:
                    return json.loads(e.read().decode("utf-8", "replace"))
                except Exception:
                    return {}
            err = e
        except Exception as e:  # red, timeout, JSON roto…
            err = e
        time.sleep(2 + 3 * k)
    raise RuntimeError(f"No se pudo leer {url}: {err}")


def ahora():
    return dt.datetime.now(MADRID).replace(tzinfo=None)


def ya_jugado(fecha):
    """fecha 'YYYY-MM-DD HH:MM' (hora de Madrid) + margen ya pasada."""
    if not fecha:
        return False
    try:
        f = dt.datetime.strptime(fecha, "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    return f + dt.timedelta(hours=MARGEN_HORAS) <= ahora()


def puntos_ok(s):
    return 2 * s["t2"][0] + 3 * s["t3"][0] + s["tl"][0] == s["pt"]


# ----------------------------------------------------------------- BueStats
def bs_lado(T, O, box, mins):
    return {"min": mins, "pt": T["pts"], "t2": [T["p2m"], T["p2a"]], "t3": [T["p3m"], T["p3a"]],
            "tl": [T["p1m"], T["p1a"]], "ro": T["oreb"], "rd": T["dreb"], "as": T["ast"], "br": T["stl"],
            "bp": T["tov"], "tf": T["blk"], "tc": O["blk"], "fc": T["pf"], "fr": O["pf"],
            "va": sum((p.get("val") or 0) for p in box)}


def bs_partido(gid):
    r = get(BUESTATS_API + f"game/{gid}", json_=True)
    tt = r.get("team_totals") or {}
    L, A = tt.get("local") or {}, tt.get("away") or {}
    if L.get("pts") is None or A.get("pts") is None:
        return None
    q = max(len((r.get("quarter_scores") or {}).get("local") or []), 4)
    mins = 200 + 25 * (q - 4)
    box = r.get("boxscore") or {}
    hs = bs_lado(L, A, box.get("local") or [], mins)
    as_ = bs_lado(A, L, box.get("away") or [], mins)
    if not (puntos_ok(hs) and puntos_ok(as_)):
        return None
    return hs, as_


def bs_calendario(g):
    cal = get(BUESTATS_API + f"league-calendar?season_id={TEMPORADA}&league_id={BUESTATS_LIGAS[g]}&scope=all", json_=True)
    out = []
    for w in cal["weeks"]:
        for x in w["games"]:
            out.append({"id": x["game_id"], "j": int(w["weekmatch"]), "h": x["local_team_name"],
                        "a": x["away_team_name"], "date": (x.get("start_date") or "").replace("T", " ")[:16],
                        "played": bool(x.get("played")), "hp": x.get("local_score"), "ap": x.get("away_score")})
    return out


# ----------------------------------------------------------------- FEB: actas
_TD = re.compile(r'<td class="([^"]+)"[^>]*>(.*?)</td>', re.S)


def _txt(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", s)).split()


def feb_acta(gid):
    """Totales de equipo del acta de la FEB. Devuelve (hs, as, local, visitante) o None si no hay acta final."""
    h = get(f"{FEB}/partido/{gid}")
    filas = re.findall(r'<tr class="row-total">(.*?)</tr>', h, re.S)
    if len(filas) < 2:
        return None
    lados = []
    for f in filas[:2]:
        c = {}
        for cls, val in _TD.findall(f):
            t = _txt(val)
            c[cls] = t[0] if t else ""
        try:
            m, s = c["minutos"].split(":")
            par = lambda k: [int(x) for x in c[k].split("/")]
            lado = {"min": round(int(m) + int(s) / 60, 2), "pt": int(c["puntos"]), "t2": par("tiros dos"),
                    "t3": par("tiros tres"), "tl": par("tiros libres"), "ro": int(c["rebotes ofensivos"]),
                    "rd": int(c["rebotes defensivos"]), "as": int(c["asistencias"]), "br": int(c["recuperaciones"]),
                    "bp": int(c["perdidas"]), "tf": int(c["tapones favor"]), "tc": int(c["tapones contra"]),
                    "fc": int(c["faltas cometidas"]), "fr": int(c["faltas recibidas"]), "va": int(c["valoracion"])}
        except (KeyError, ValueError):
            return None
        if lado["min"] < 199 or not puntos_ok(lado):   # partido en directo o acta incompleta
            return None
        lados.append(lado)
    nombres = re.findall(r'equipo(?:Local|Visitante)Nombre">([^<]+)<', h)
    nombres = [ALIAS.get(htmllib.unescape(n).strip(), htmllib.unescape(n).strip()) for n in nombres] + ["", ""]
    return lados[0], lados[1], nombres[0], nombres[1]


# ----------------------------------------------------------------- FEB: Copa España
def _ocultos(h):
    out = {}
    for tag in re.findall(r"<input[^>]+>", h):
        if 'type="hidden"' not in tag:
            continue
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            out[htmllib.unescape(n.group(1))] = htmllib.unescape(v.group(1)) if v else ""
    return out


def _select(h, sufijo):
    m = re.search(r'<select name="([^"]*' + sufijo + r')"[^>]*>(.*?)</select>', h, re.S)
    if not m:
        return None, [], None
    opts = re.findall(r'<option(?: selected="selected")? value="([^"]*)">([^<]*)</option>', m.group(2))
    sel = re.search(r'<option selected="selected" value="([^"]*)"', m.group(2))
    return m.group(1), [(v, htmllib.unescape(t).strip()) for v, t in opts], (sel.group(1) if sel else None)


def _postback(h, sufijo, valor):
    campos = _ocultos(h)
    for suf in ("temporadasDropDownList", "gruposDropDownList", "jornadasDropDownList"):
        r = _select(h, suf)
        if r[0]:
            campos[r[0]] = r[2] or (r[1][0][0] if r[1] else "")
    nombre = _select(h, sufijo)[0]
    campos[nombre] = valor
    campos["__EVENTTARGET"] = nombre.replace(":", "$")
    campos["__EVENTARGUMENT"] = ""
    return get(COPA_URL, data=campos)


_FILA_COPA = re.compile(
    r'equipoLocalHyperLink"[^>]*>([^<]+)</a>.*?equipoVisitHyperLink"[^>]*>([^<]+)</a>.*?'
    r'resultadoHyperLink"[^>]*href="[^"]*p=(\d+)"[^>]*>([^<]*)</a>\s*</td>\s*<td>\s*(\d\d/\d\d/\d{4})\s*</td>\s*<td>\s*(\d\d:\d\d)?',
    re.S)


def _ronda(texto):
    t = texto.lower()
    if "grupo" in t:
        return "Fase de grupos"
    for k, v in (("1/16", "Dieciseisavos"), ("1/8", "Octavos"), ("1/4", "Cuartos"),
                 ("1/2", "Semifinales"), ("semif", "Semifinales"), ("final", "Final")):
        if k in t:
            return v
    return texto.strip()


def copa_partidos(equipos_a):
    h0 = get(COPA_URL)
    _, grupos, _ = _select(h0, "gruposDropDownList")
    vistos = {}
    for gv, gtxt in grupos:
        hg = _postback(h0, "gruposDropDownList", gv)
        _, jornadas, selj = _select(hg, "jornadasDropDownList")
        # La FEB ya muestra la jornada seleccionada al cambiar de fase; volver a pedirla
        # devuelve la página vacía, así que solo se piden las demás jornadas.
        paginas = [hg] + [_postback(hg, "jornadasDropDownList", jv) for jv, _ in jornadas if jv != selj]
        for h in paginas:
            for loc, vis, pid, res, fecha, hora in _FILA_COPA.findall(h):
                loc = ALIAS.get(htmllib.unescape(loc).strip(), htmllib.unescape(loc).strip())
                vis = ALIAS.get(htmllib.unescape(vis).strip(), htmllib.unescape(vis).strip())
                d, m, y = fecha.split("/")
                vistos[int(pid)] = {"id": int(pid), "rnd": _ronda(gtxt), "h": loc, "a": vis, "res": res.strip(),
                                    "date": f"{y}-{m}-{d} {hora or '00:00'}"}
    out = []
    for p in sorted(vistos.values(), key=lambda x: x["date"]):
        if p["h"] not in equipos_a and p["a"] not in equipos_a:
            continue
        if not re.match(r"^\d+-\d+$", p["res"]) or not ya_jugado(p["date"]):
            continue
        acta = feb_acta(p["id"])
        if not acta:
            log(f"  Copa {p['id']} ({p['h']} – {p['a']}): sin acta todavía")
            continue
        hs, as_, _, _ = acta
        out.append({"id": p["id"], "rnd": p["rnd"], "date": p["date"], "h": p["h"], "a": p["a"], "hs": hs, "as": as_})
    return out


# ----------------------------------------------------------------- principal
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def main():
    previo = json.load(open(os.path.join(AQUI, "data.json"), encoding="utf-8"))
    fijos = {k: previo.get(k) for k in ("names", "crests", "logo")}
    avisos = []

    # 1) calendario de BueStats (si falla, se reutiliza el anterior)
    cal = {}
    try:
        for g in ("A", "B"):
            cal[g] = bs_calendario(g)
            log(f"BueStats grupo {g}: {len(cal[g])} partidos en el calendario")
    except Exception as e:
        avisos.append(f"BueStats no respondió ({e}); se usa el calendario anterior.")
        log(avisos[-1])
        T = previo["sched"]["teams"]
        prev_games = {x["id"]: x for x in previo["games"]}
        cal = {g: [{"id": s[0], "j": s[1], "h": T[s[2]], "a": T[s[3]], "date": s[4],
                    "played": s[0] in prev_games, "hp": None, "ap": None} for s in previo["sched"][g]]
               for g in ("A", "B")}

    # 2) partidos de liga
    prev_by_id = {x["id"]: x for x in previo.get("games", [])}
    games, scores = [], []
    bs_ok = bool(cal) and not avisos
    for g in ("A", "B"):
        for s in cal[g]:
            if not (s["played"] or ya_jugado(s["date"])):
                continue
            par = None
            src = None
            if bs_ok and s["played"]:
                try:
                    par = bs_partido(s["id"])
                    src = "BueStats" if par else None
                except Exception as e:
                    log(f"  BueStats {s['id']}: {e}")
            if not par and ya_jugado(s["date"]):
                try:
                    a = feb_acta(s["id"])
                    if a:
                        par, src = (a[0], a[1]), "FEB"
                except Exception as e:
                    log(f"  FEB {s['id']}: {e}")
            if not par and not bs_ok and s["id"] in prev_by_id:      # sin red: conservar lo que había
                x = prev_by_id[s["id"]]
                par, src = (x["hs"], x["as"]), x.get("src", "BueStats")
            if par:
                x = {"id": s["id"], "g": g, "j": s["j"], "h": s["h"], "a": s["a"], "hs": par[0], "as": par[1]}
                if src == "FEB":
                    x["src"] = "FEB"
                games.append(x)
            elif s["played"] and s["hp"] is not None:
                scores.append({"id": s["id"], "g": g, "j": s["j"], "h": s["h"], "a": s["a"], "hp": s["hp"], "ap": s["ap"]})
    games.sort(key=lambda x: x["id"])
    log(f"Liga: {len(games)} partidos con estadísticas ({sum(1 for x in games if x.get('src') == 'FEB')} de la FEB), "
        f"{len(scores)} solo con resultado")

    # 3) calendario en formato compacto
    teams = list(previo["sched"]["teams"])
    def ti(n):
        if n not in teams:
            teams.append(n)
        return teams.index(n)
    sched = {"teams": teams}
    for g in ("A", "B"):
        sched[g] = sorted([[s["id"], s["j"], ti(s["h"]), ti(s["a"]), s["date"]] for s in cal[g]], key=lambda r: (r[1], r[0]))

    # 4) Copa España (equipos del Grupo A)
    equipos_a = {s["h"] for s in cal["A"]} | {s["a"] for s in cal["A"]}
    try:
        copa = copa_partidos(equipos_a)
        log(f"Copa España: {len(copa)} partidos de equipos del Grupo A")
    except Exception as e:
        copa = previo.get("copa", [])
        avisos.append(f"No se pudo leer la Copa en la FEB ({e}); se mantienen los partidos de copa anteriores.")
        log(avisos[-1])

    # 5) guardar
    n = ahora()
    mj = lambda g: max([x["j"] for x in games + scores if x["g"] == g] or [0])
    data = {"games": games, "scores": scores, "copa": copa, "sched": sched, **fijos,
            "updated": f"Actualizado el {n.day} de {MESES[n.month - 1]} de {n.year} a las {n:%H:%M} · "
                       f"Grupo A hasta la J{mj('A')} · Grupo B hasta la J{mj('B')}"}
    if not games:
        sys.exit("No se ha obtenido ningún partido: no se guarda nada para no estropear la web.")
    json.dump(data, open(os.path.join(AQUI, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    plantilla = open(os.path.join(AQUI, "plantilla.html"), encoding="utf-8").read()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    pagina = plantilla.replace("__REPO__", repo).replace("__DATA__", js)
    open(os.path.join(AQUI, "index.html"), "w", encoding="utf-8").write(pagina)
    log("Listo:", data["updated"])
    for a in avisos:
        log("AVISO:", a)


if __name__ == "__main__":
    main()
