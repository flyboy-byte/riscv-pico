"""Routing helpers for a generated KiCad board (pcbnew Python API, KiCad 10).

    import finish_routes
    finish_routes.negotiate(board, ['/NET_A', '/NET_B', ...], local={'+5V': (x0, y0, x1, y1)})
        Negotiated routing (PathFinder) of a group of nets before the autorouter runs: all nets are routed, may share
        space at a cost that rises each round, are ripped up and rerouted until none are too close. The result is
        locked so the autorouter works around it. Use it for a dense local group (an analog stage) that one-at-a-time
        routing keeps walling in. `local` limits a big net to its copper inside a box.
    finish_routes.finish(board, pcb_path)
        After the autorouter: routes each connection DRC still lists as unconnected (non-GND) with A* on a 0.1 mm grid.

Rules (edit the constants): track W, clearance CLEAR (board rule + grid margin), EDGE, HOLE, via size. Obstacles are
other nets' pads, tracks and vias, holes, the board edge and cutouts, rule areas that forbid tracks or vias (those named
in env FINISH_IGNORE are skipped), a free ring round top-side SMD GND pads so pours still reach them, and every SMD pad
for vias. Pours are not obstacles; they refill. DRC judges the result. `[reported: wideband carrier, 2026-10-23]`
"""
import heapq, json, math, os, subprocess, tempfile

import pcbnew

G = 0.1           # grid, mm
W = 0.25          # track width, mm
CLEAR = 0.25      # copper clearance: board rule 0.2 + 0.05 for grid rounding and diagonal corners, mm
EDGE = 0.5        # copper to edge (board rule), mm
GND_RING = 0.5    # extra free ring around SMD GND pads for the pour, mm
HOLE = 0.3        # copper to hole edge: board rule 0.25 + margin, mm
VIA, DRILL = 0.6, 0.3
VIA_COST = 2.0    # mm of track a via is worth
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
T = pcbnew.ToMM


def mm(v):
    return pcbnew.FromMM(v)


def open_connections(pcb_path):
    """[(net, (x, y), (x, y))] for non-GND unconnected pairs, from kicad-cli DRC."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'd.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', out, pcb_path], capture_output=True)
        d = json.load(open(out))
    pairs = []
    for u in d.get('unconnected_items', []):
        items = u['items']
        if len(items) != 2:
            continue
        net = items[0]['description'].split('[', 1)[-1].split(']', 1)[0]
        if net == 'GND' or 'Zone' in items[0]['description'] or 'Zone' in items[1]['description']:
            continue
        pairs.append((net, (items[0]['pos']['x'], items[0]['pos']['y']), (items[1]['pos']['x'], items[1]['pos']['y'])))
    return pairs


class Grid:
    def __init__(self, board):
        self.board = board
        e = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = T(e.GetX()), T(e.GetY())
        self.nx, self.ny = int(T(e.GetWidth()) / G) + 1, int(T(e.GetHeight()) / G) + 1
        self.edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
        self.edges += [g for f in board.GetFootprints() for g in f.GraphicalItems() if g.GetLayer() == pcbnew.Edge_Cuts]
        outline = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(outline, True)
        self.outline = outline
        self.keepouts = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() not in os.environ.get('FINISH_IGNORE', '').split(',')]

    def pt(self, i, j):
        return pcbnew.VECTOR2I(mm(self.x0 + i * G), mm(self.y0 + j * G))

    def cells_near(self, bbox, margin):
        i0 = max(0, int((T(bbox.GetX()) - margin - self.x0) / G))
        j0 = max(0, int((T(bbox.GetY()) - margin - self.y0) / G))
        i1 = min(self.nx - 1, int((T(bbox.GetRight()) + margin - self.x0) / G) + 1)
        j1 = min(self.ny - 1, int((T(bbox.GetBottom()) + margin - self.y0) / G) + 1)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield i, j

    def blocked(self, net, r):
        """Per layer, the set of cells where copper of radius r on `net` would break a rule."""
        out = {l: set() for l in LAYERS}
        items = [p for f in self.board.GetFootprints() for p in f.Pads() if p.IsOnCopperLayer()]
        items += list(self.board.GetTracks())
        for it in items:
            # vias stay out of every SMD pad, own net included (solder wicks down a via in a pad)
            own_smd_for_via = r >= VIA / 2 and it.Type() == pcbnew.PCB_PAD_T and it.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
            if it.GetNetname() == net and net and not own_smd_for_via:
                continue
            for l in LAYERS:
                if not it.IsOnLayer(l):
                    continue
                # a top-side SMD GND pad keeps a wider ring free so the pour can still reach it (new tracks cut C2 and C6
                # off the top GND pour on r20)
                gap = r + CLEAR
                if l == pcbnew.F_Cu and net != 'GND' and it.GetNetname() == 'GND' and it.Type() == pcbnew.PCB_PAD_T and \
                        it.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    gap += GND_RING
                for i, j in self.cells_near(it.GetBoundingBox(), gap):
                    if (i, j) not in out[l] and it.HitTest(self.pt(i, j), mm(gap)):
                        out[l].add((i, j))
        # holes (mounting holes, unplated connector pegs) block both layers: hole clearance HOLE from the drill edge
        edge_cells = set()
        for f in self.board.GetFootprints():
            for p in f.Pads():
                if p.GetDrillSize().x <= 0 or (p.GetNetname() == net and net):
                    continue
                c, rad = p.GetPosition(), T(p.GetDrillSize().x) / 2 + HOLE + r
                for i, j in self.cells_near(p.GetBoundingBox(), HOLE + r):
                    q = self.pt(i, j)
                    if math.hypot(T(q.x - c.x), T(q.y - c.y)) < rad:
                        edge_cells.add((i, j))
        # board edge and cutout: every cell closer than EDGE + r to an Edge.Cuts line, or outside the board
        for d in self.edges:
            for i, j in self.cells_near(d.GetBoundingBox(), r + EDGE):
                if d.HitTest(self.pt(i, j), mm(r + EDGE)):
                    edge_cells.add((i, j))
        for i in range(self.nx):
            for j in range(self.ny):
                if not self.outline.Contains(self.pt(i, j)):
                    edge_cells.add((i, j))
        for l in LAYERS:
            out[l] |= edge_cells
        return out

    def rule_area_cells(self, kind):
        out = {l: set() for l in LAYERS}
        for z in self.keepouts:
            if (kind == 'track' and not z.GetDoNotAllowTracks()) or (kind == 'via' and not z.GetDoNotAllowVias()):
                continue
            poly = z.Outline()
            for l in LAYERS:
                if not z.IsOnLayer(l):
                    continue
                for i, j in self.cells_near(z.GetBoundingBox(), 0):
                    if poly.Contains(self.pt(i, j)):
                        out[l].add((i, j))
        return out


def item_cells(board, grid, net, xy):
    """(layer, i, j) cells covered by the copper item of `net` at DRC position xy (a pad, track or via)."""
    p = pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1]))
    items = [q for f in board.GetFootprints() for q in f.Pads() if q.GetNetname() == net]
    items += [t for t in board.GetTracks() if t.GetNetname() == net]
    hit = [it for it in items if it.HitTest(p, mm(0.05))]
    if not hit:
        return set()
    it = hit[0]
    cells = set()
    for l in LAYERS:
        if it.IsOnLayer(l):
            for i, j in grid.cells_near(it.GetBoundingBox(), 0):
                if it.HitTest(grid.pt(i, j), 0):
                    cells.add((l, i, j))
    return cells


def astar(grid, start, goal, block_track, block_via):
    gl = list(goal)
    gx = sum(c[1] for c in gl) / len(gl)
    gy = sum(c[2] for c in gl) / len(gl)

    def h(i, j):
        return math.hypot(i - gx, j - gy) * G * 0.9

    dist, prev, pq = {}, {}, []
    for c in start:
        dist[c] = 0.0
        heapq.heappush(pq, (h(c[1], c[2]), 0.0, c))
    steps = [(1, 0, G), (-1, 0, G), (0, 1, G), (0, -1, G),
             (1, 1, G * 1.4142), (1, -1, G * 1.4142), (-1, 1, G * 1.4142), (-1, -1, G * 1.4142)]
    while pq:
        f, d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e9):
            continue
        if c in goal:
            path = [c]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1]
        l, i, j = c
        nbrs = []
        for di, dj, cost in steps:
            n = (l, i + di, j + dj)
            if 0 <= n[1] < grid.nx and 0 <= n[2] < grid.ny and ((n[1], n[2]) not in block_track[l] or n in goal):
                nbrs.append((n, cost))
        other = LAYERS[1] if l == LAYERS[0] else LAYERS[0]
        if all((i, j) not in block_via[k] for k in LAYERS):
            nbrs.append(((other, i, j), VIA_COST))
        for n, cost in nbrs:
            nd = d + cost
            if nd < dist.get(n, 1e9):
                dist[n] = nd
                prev[n] = c
                heapq.heappush(pq, (nd + h(n[1], n[2]), nd, n))
    return None


def add_path(board, grid, net, path, lock=False):
    """Track segments (collinear runs merged) and vias along a grid path."""
    n = board.FindNet(net)
    added = 0
    run = [path[0]]

    def flush(run):
        if len(run) < 2:
            return 0
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(grid.pt(run[0][1], run[0][2])); t.SetEnd(grid.pt(run[-1][1], run[-1][2]))
        t.SetWidth(mm(W)); t.SetLayer(run[0][0]); t.SetNet(n); t.SetLocked(lock)
        board.Add(t)
        return 1

    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            added += flush(run)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(grid.pt(a[1], a[2])); v.SetWidth(mm(VIA)); v.SetDrill(mm(DRILL)); v.SetNet(n); v.SetLocked(lock)
            board.Add(v)
            run = [b]
            continue
        if len(run) >= 2:
            d0 = (run[-1][1] - run[-2][1], run[-1][2] - run[-2][2])
            if (b[1] - a[1], b[2] - a[2]) != d0:
                added += flush(run)
                run = [a]
        run.append(b)
    added += flush(run)
    return added


def finish(board, pcb_path, only=None, lock=False):
    """Route open pairs; `only` limits it to those nets (in that order), `lock` locks the result (pre-routing)."""
    pairs = open_connections(pcb_path)
    if only:
        pairs = sorted((p for p in pairs if p[0] in only), key=lambda p: only.index(p[0]))
    if not pairs:
        print('finisher: nothing open')
        return 0
    grid = Grid(board)
    keep_track, keep_via = grid.rule_area_cells('track'), grid.rule_area_cells('via')
    done = 0
    for net, a, b in pairs:
        start, goal = item_cells(board, grid, net, a), item_cells(board, grid, net, b)
        if not start or not goal:
            print(f'finisher: {net}: could not find the items at {a} / {b}')
            continue
        bt = grid.blocked(net, W / 2)
        bv = grid.blocked(net, VIA / 2)
        for l in LAYERS:
            bt[l] |= keep_track[l]
            bv[l] |= keep_via[l]
        path = astar(grid, start, goal, bt, bv)
        if not path:
            print(f'finisher: {net}: no path')
            continue
        segs = add_path(board, grid, net, path, lock)
        vias = sum(1 for p, q in zip(path, path[1:]) if p[0] != q[0])
        print(f'finisher: {net}: {segs} segments, {vias} vias, {len(path) * G:.1f} mm')
        done += 1
    return done


# ---------------------------------------------------------------------------------------------------------------
# Negotiated routing (PathFinder) for a group of nets: route all of them, let them share space at a cost that grows
# each round (present + history), rip up and repeat until no two nets are too close. One-at-a-time routing of the
# analog stage's nets moved the failure from net to net with every ordering (r17-r19, 2026-10-23).
# ---------------------------------------------------------------------------------------------------------------
def _disc(r):
    n = int(math.ceil(r / G))
    import numpy as np
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return (x * x + y * y) * G * G < r * r


def _terminals(board, grid, net, box=None):
    """Cell sets (layer index, i, j) of every copper item already on `net`: pads and existing tracks/vias; only
    those whose centre lies in `box` (x0, y0, x1, y1 mm) when given."""
    items = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == net and p.IsOnCopperLayer()]
    items += [t for t in board.GetTracks() if t.GetNetname() == net]
    out = []
    for it in items:
        if box:
            c = it.GetBoundingBox().GetCenter()
            if not (box[0] <= T(c.x) <= box[2] and box[1] <= T(c.y) <= box[3]):
                continue
        cells = set()
        for k, l in enumerate(LAYERS):
            if it.IsOnLayer(l):
                for i, j in grid.cells_near(it.GetBoundingBox(), 0):
                    if it.HitTest(grid.pt(i, j), 0):
                        cells.add((k, i, j))
        if cells:
            out.append(cells)
    return out


def negotiate(board, nets, rounds=80, local=None):
    """`local`: {net: box} routes only that net's copper inside the box (a big net's local branch)."""
    local = local or {}
    import numpy as np
    from scipy.ndimage import binary_dilation
    grid = Grid(board)
    shape = (2, grid.nx, grid.ny)
    keep_t, keep_v = grid.rule_area_cells('track'), grid.rule_area_cells('via')
    static = {}
    for n in nets:
        bt, bv = np.zeros(shape, bool), np.zeros(shape, bool)
        blk_t, blk_v = grid.blocked(n, W / 2), grid.blocked(n, VIA / 2)
        for k, l in enumerate(LAYERS):
            for (i, j) in blk_t[l] | keep_t[l]:
                bt[k, i, j] = True
            for (i, j) in blk_v[l] | keep_v[l]:
                bv[k, i, j] = True
        static[n] = (bt, bv[0] | bv[1])
    terms = {n: _terminals(board, grid, n, local.get(n)) for n in nets}
    # conflict distances between centrelines: track-track W+CLEAR, track-via VIA/2+CLEAR+W/2, via-via VIA+CLEAR
    d_tt, d_tv, d_vv = W + CLEAR, VIA / 2 + CLEAR + W / 2, VIA + CLEAR
    disc = {k: _disc(v) for k, v in (('tt', d_tt), ('tv', d_tv), ('vv', d_vv))}
    hist = np.zeros(shape)
    cov_t = {n: np.zeros(shape, np.int8) for n in nets}   # where this net's copper keeps other tracks out
    cov_v = {n: np.zeros(shape[1:], np.int8) for n in nets}   # ... keeps other vias out (both layers)
    paths = {}

    def footprint(path):
        tr, vi = np.zeros(shape, bool), np.zeros(shape[1:], bool)
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                vi[a[1], a[2]] = True
        for c in path:
            tr[c] = True
        ct = np.zeros(shape, bool)
        for k in range(2):
            ct[k] = binary_dilation(tr[k], disc['tt']) | binary_dilation(vi, disc['tv'])
        cv = binary_dilation(tr[0] | tr[1], disc['tv']) | binary_dilation(vi, disc['vv'])
        return ct, cv, tr, vi

    def route(n, pres):
        bt, bv = static[n]
        others_t = sum(cov_t[o] for o in nets if o != n and o in paths)
        others_v = sum(cov_v[o] for o in nets if o != n and o in paths)
        if not isinstance(others_t, np.ndarray):
            others_t, others_v = np.zeros(shape), np.zeros(shape[1:])
        cost_t = (1 + hist) * (1 + pres * others_t)
        cost_v = (1 + hist[0] + hist[1]) * (1 + pres * others_v)
        ts = [t for t in terms[n]]
        if len(ts) < 2:
            return []
        tree = set(ts[0])
        rest = ts[1:]
        full = []

        def absorb():
            # pieces touching the tree (existing copper already joined to it) become part of it, transitively
            nonlocal rest
            grown = True
            while grown:
                grown = False
                for t in list(rest):
                    if t & tree:
                        tree.update(t)
                        rest.remove(t)
                        grown = True
        absorb()
        while rest:
            goal = set().union(*rest)
            p = _astar_cost(grid, tree, goal, bt, bv, cost_t, cost_v)
            if p is None:
                return None
            full += p
            tree.update(p)
            absorb()
        return full

    pres = 0.5
    for rnd in range(rounds):
        for n in nets:
            paths.pop(n, None)
            p = route(n, pres)
            if p is None:
                continue
            paths[n] = p
            ct, cv, _, _ = footprint(p)
            cov_t[n], cov_v[n] = ct.astype(np.int8), cv.astype(np.int8)
        # conflicts: a net's own centreline cells inside another net's keep-out
        bad = set()
        over = np.zeros(shape)
        for n, p in paths.items():
            _, _, tr, vi = footprint(p)
            ot = sum(cov_t[o] for o in paths if o != n)
            ov = sum(cov_v[o] for o in paths if o != n)
            if isinstance(ot, np.ndarray) and ((tr & (ot > 0)).any() or (vi & (ov > 0)).any()):
                bad.add(n)
                over += tr * (ot > 0)
        unrouted = [n for n in nets if n not in paths and len(terms[n]) > 1]
        print(f'negotiate round {rnd}: {len(bad)} nets in conflict, {len(unrouted)} unroutable')
        if not bad and not unrouted:
            break
        hist += 0.8 * (over > 0)
        pres *= 1.6
    good = [n for n in paths if n not in bad]
    for n in good:
        p = paths[n]
        if not p:
            continue
        # split the concatenated tree segments where consecutive cells are not neighbours
        seg = [p[0]]
        for c in p[1:]:
            last = seg[-1]
            if abs(c[1] - last[1]) > 1 or abs(c[2] - last[2]) > 1:
                _commit(board, grid, n, seg)
                seg = [c]
            else:
                seg.append(c)
        _commit(board, grid, n, seg)
    print(f'negotiate: committed {len(good)} of {len(nets)} nets (locked); left to the router: {sorted(set(nets) - set(good))}')
    return good


def _commit(board, grid, net, cells):
    if len(cells) < 2:
        return
    add_path(board, grid, net, [(LAYERS[c[0]], c[1], c[2]) for c in cells], lock=True)


def _astar_cost(grid, start, goal, bt, bv, cost_t, cost_v):
    gl = list(goal)
    gx = sum(c[1] for c in gl) / len(gl)
    gy = sum(c[2] for c in gl) / len(gl)
    dist, prev, pq = {}, {}, []
    for c in start:
        dist[c] = 0.0
        heapq.heappush(pq, (0.0, 0.0, c))
    steps = [(1, 0, G), (-1, 0, G), (0, 1, G), (0, -1, G),
             (1, 1, G * 1.4142), (1, -1, G * 1.4142), (-1, 1, G * 1.4142), (-1, -1, G * 1.4142)]
    nx, ny = grid.nx, grid.ny
    while pq:
        f, d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18):
            continue
        if c in goal:
            path = [c]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1]
        k, i, j = c
        for di, dj, step in steps:
            ni, nj = i + di, j + dj
            if not (0 <= ni < nx and 0 <= nj < ny):
                continue
            n = (k, ni, nj)
            if bt[k, ni, nj] and n not in goal:
                continue
            nd = d + step * cost_t[k, ni, nj]
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = c
                heapq.heappush(pq, (nd + math.hypot(ni - gx, nj - gy) * G * 0.5, nd, n))
        if not bv[i, j]:
            n = (1 - k, i, j)
            nd = d + VIA_COST * cost_v[i, j]
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = c
                heapq.heappush(pq, (nd + math.hypot(i - gx, j - gy) * G * 0.5, nd, n))
    return None
