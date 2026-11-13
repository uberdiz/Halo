// HalOS look, once per user: the taskbar floats a little above the screen edge with rounded corners and blur
// behind it (Plasma's floating panel; it settles flush against the edge when a window is maximised), and is a
// touch taller so icons have room to breathe. A file of its own so accounts that already ran the other update
// scripts get it too. Someone who already chose a non-floating panel (floating false written before) keeps it
// after this runs once: Plasma never runs an update script twice.
var ps = panels();
for (var i = 0; i < ps.length; i++) {
    var p = ps[i];
    if (p.location !== "bottom" && p.location !== "top")
        continue;                       // side panels are someone's own layout
    p.floating = true;
    if (p.height < 44)
        p.height = 44;
}
