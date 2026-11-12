// HalOS: the HalOS start button and a desktop Pager, for every user, once. A file of its own because Plasma
// runs each update script once per user: accounts that already ran saintos-defaults.js still get this one.
// Plasma 6's default panel may already hold a Pager: then it's left where it is.
var ps = panels();
var pagerDone = false;
for (var p = 0; p < ps.length; p++) { if (ps[p].widgets("org.kde.plasma.pager").length) pagerDone = true; }

for (var i = 0; i < ps.length; i++) {
    var ws = ps[i].widgets();
    var launcher = -1;
    for (var w = 0; w < ws.length; w++) {
        var t = ws[w].type;
        if (t === "org.kde.plasma.kickoff" || t === "org.kde.plasma.kicker") {
            ws[w].currentConfigGroup = ["General"];
            ws[w].writeConfig("icon", "halos");
            if (launcher < 0) launcher = w;
        }
    }
    if (launcher >= 0 && !pagerDone) {
        var pager = ps[i].addWidget("org.kde.plasma.pager");
        pagerDone = true;
        // Right after the start button: a panel keeps its order in General/AppletOrder (applet ids).
        var order = [];
        for (var o = 0; o < ws.length; o++) {
            order.push(ws[o].id);
            if (o === launcher) order.push(pager.id);
        }
        ps[i].currentConfigGroup = ["General"];
        ps[i].writeConfig("AppletOrder", order.join(";"));
    }
}
