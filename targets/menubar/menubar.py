#!/usr/bin/env python3
"""Extras da barra de menu (painel do topo).

  get <central>              imprime "applied" se a barra tem o Window Title e o Control Station
                             só se <central> for true
  set <formato> <desktop> <negrito> <central>
                             põe o Window Title logo depois do menu (maçã) e, com <central> true,
                             o Control Station antes do relógio (sem ele, tira); a ordem vai no
                             appletsrc com o plasmashell parado
  restore <valor>            valor vazio: tira os dois widgets da barra
"""
import json
import subprocess
import sys
import time

TITLE, CONTROL = "org.kde.windowtitle", "KdeControlStation"


def shell(script):
    return subprocess.run(["qdbus6", "org.kde.plasmashell", "/PlasmaShell",
                           "org.kde.PlasmaShell.evaluateScript", script],
                          capture_output=True, text=True, check=True).stdout


def bar():
    out = shell("""var b = panels().filter(function (p) { return p.location == "top"; })[0];
        if (b) { b.currentConfigGroup = ["General"];
          print(JSON.stringify({id: b.id, order: String(b.readConfig("AppletOrder")),
            widgets: b.widgets().map(function (w) { return [w.id, w.type]; })})); }""")
    return json.loads(out) if out.strip() else None


def has(b, kind):
    return [i for i, t in b["widgets"] if t == kind]


def restart_with_order(panel, order):
    subprocess.run(["kquitapp6", "plasmashell"], capture_output=True)
    time.sleep(1)
    subprocess.run(["kwriteconfig6", "--file", "plasma-org.kde.plasma.desktop-appletsrc",
                    "--group", "Containments", "--group", str(panel), "--group", "General",
                    "--key", "AppletOrder", ";".join(map(str, order))], check=True)
    subprocess.Popen(["setsid", "kstart", "plasmashell"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    action = sys.argv[1]
    b = bar()
    if action == "get":
        want = sys.argv[2:3] == ["true"]
        ok = b and has(b, TITLE) and bool(has(b, CONTROL)) == want
        print("applied" if ok else "")
        return
    if b is None:
        raise SystemExit("menubar: sem painel no topo")
    if action == "restore":
        if sys.argv[2:3] == [""] or len(sys.argv) < 3:
            shell(f"""var b = panelById({b['id']});
                b.widgets().forEach(function (w) {{ if (w.type == {json.dumps(TITLE)} || w.type == {json.dumps(CONTROL)}) w.remove(); }});""")
        return
    fmt, desktop, bold, central = sys.argv[2:6]
    central = central == "true"
    shell(f"""var b = panelById({b['id']});
        var t = b.widgets({json.dumps(TITLE)})[0] || b.addWidget({json.dumps(TITLE)});
        t.currentConfigGroup = ["General"];
        t.writeConfig("txt", {json.dumps(fmt)});
        t.writeConfig("txtSameFound", {json.dumps(fmt)});
        t.writeConfig("altTxt", {json.dumps(desktop)});
        t.writeConfig("isBold", {json.dumps(bold == "true")});
        t.writeConfig("visible", false);   // checkbox "mostrar ícone" do widget
        if ({json.dumps(central)}) {{ if (!b.widgets({json.dumps(CONTROL)}).length) b.addWidget({json.dumps(CONTROL)}); }}
        else b.widgets({json.dumps(CONTROL)}).forEach(function (w) {{ w.remove(); }});""")
    b = bar()
    ids = {t: i for i, t in b["widgets"]}
    order = [int(x) for x in b["order"].split(";") if x] or [i for i, _ in b["widgets"]]
    order = [i for i in order if i in ids.values() and i not in (ids[TITLE], ids.get(CONTROL))]
    # Window Title depois do menu da maçã (kickoff); Control Station antes do relógio.
    kick = ids.get("org.kde.plasma.kickoff")
    order.insert(order.index(kick) + 1 if kick in order else 0, ids[TITLE])
    if central:
        clock = ids.get("org.kde.plasma.digitalclock")
        order.insert(order.index(clock) if clock in order else len(order), ids[CONTROL])
    restart_with_order(b["id"], order)


main()
