// ${theme_name}: layout estilo macOS. Gerado de targets/layout/templates/layout.js.
// Idempotente. Em painéis que já existem, só tira o "mostrar área de trabalho" da barra
// do topo (o macOS não tem). Numa máquina sem painéis, cria a barra de menu e a Dock.
// Relógio, Launchpad e Lixeira ficam de fora.

function find(location) {
    var all = panels();
    for (var i = 0; i < all.length; i++) {
        if (all[i].location == location) return all[i];
    }
    return null;
}

// --- Barra de menu (topo) ---------------------------------------------------------
var bar = find("top");
if (!bar) {
    bar = new Panel("org.kde.panel");
    bar.location = "top";
    bar.height = ${layout_menubar_height};
    bar.floating = false;
    ["org.kde.plasma.kickoff", "org.kde.plasma.appmenu", "org.kde.plasma.panelspacer",
     "org.kde.plasma.systemtray", "org.kde.plasma.digitalclock"].forEach(function (t) { bar.addWidget(t); });
}
bar.widgets("org.kde.plasma.showdesktop").forEach(function (w) { w.remove(); });

// --- Dock (embaixo) ---------------------------------------------------------------
if (!find("bottom")) {
    var dock = new Panel("org.kde.panel");
    dock.location = "bottom";
    dock.height = ${layout_dock_height};
    dock.floating = true;
    dock.lengthMode = "fit";
    dock.alignment = "center";
    dock.hiding = "dodgewindows";
    dock.addWidget("org.kde.plasma.icontasks");
}
print("layout ok\n");
