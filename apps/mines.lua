-- mines.lua: minesweeper for the riscv-pico VGA console.
--
-- Fits the 53x30 character screen the VGA terminal gives you, and uses only the escape sequences
-- that terminal actually implements: clear screen, cursor position, clear to end of line, and the
-- eight colours. Nothing else is safe here -- the terminal prints unknown sequences as text.
--
-- Arrow keys need key-at-a-time input, which needs sys.raw() from the Lua sys extension. Without a
-- terminal (piped input, for instance) it falls back to typed commands, so it still works over a
-- pipe or a script.
--
-- usage: lua mines.lua [width] [height] [mines]

local W = tonumber(arg and arg[1]) or 16
local H = tonumber(arg and arg[2]) or 12
local MINES = tonumber(arg and arg[3]) or 25

if W < 4 then W = 4 elseif W > 24 then W = 24 end
if H < 4 then H = 4 elseif H > 20 then H = 20 end
local maxmines = math.floor(W * H / 3)
if MINES < 1 then MINES = 1 elseif MINES > maxmines then MINES = maxmines end

local ESC = string.char(27)
local function at(row, col) return ESC .. "[" .. row .. ";" .. col .. "H" end
local CLEAR, EOL, RESET = ESC .. "[2J", ESC .. "[K", ESC .. "[m"
local COLOUR = {}
for i = 0, 7 do COLOUR[i] = ESC .. "[3" .. i .. "m" end

-- number colours, roughly the usual minesweeper ones within eight colours
local NUMCOL = {COLOUR[4], COLOUR[2], COLOUR[1], COLOUR[5], COLOUR[1], COLOUR[6], COLOUR[7], COLOUR[7]}

local mine, shown, flag = {}, {}, {}
local cx, cy, alive, won, started, message

local function idx(x, y) return (y - 1) * W + x end

local function reset()
  mine, shown, flag = {}, {}, {}
  for i = 1, W * H do mine[i], shown[i], flag[i] = false, false, false end
  cx, cy, alive, won, started = 1, 1, true, false, false
  message = "arrows move  space digs  f flag  r restart  q quit"
end

-- mines are placed after the first dig, so the first move is never a loss
local function place(fx, fy)
  local placed = 0
  while placed < MINES do
    local x = math.random(W)
    local y = math.random(H)
    local i = idx(x, y)
    if not mine[i] and not (x == fx and y == fy) then
      mine[i] = true
      placed = placed + 1
    end
  end
  started = true
end

local function neighbours(x, y, fn)
  for dy = -1, 1 do
    for dx = -1, 1 do
      local nx, ny = x + dx, y + dy
      if not (dx == 0 and dy == 0) and nx >= 1 and nx <= W and ny >= 1 and ny <= H then
        fn(nx, ny, idx(nx, ny))
      end
    end
  end
end

local function count(x, y)
  local n = 0
  neighbours(x, y, function(_, _, i) if mine[i] then n = n + 1 end end)
  return n
end

local function flagsLeft()
  local n = MINES
  for i = 1, W * H do if flag[i] then n = n - 1 end end
  return n
end

-- iterative flood fill: recursion would be deep on a big empty board
local function dig(x, y)
  local i = idx(x, y)
  if shown[i] or flag[i] then return end
  if not started then place(x, y) end
  if mine[i] then
    alive = false
    message = "boom. r restarts, q quits"
    return
  end
  local stack = {{x, y}}
  while #stack > 0 do
    local cell = table.remove(stack)
    local sx, sy = cell[1], cell[2]
    local si = idx(sx, sy)
    if not shown[si] and not flag[si] then
      shown[si] = true
      if count(sx, sy) == 0 then
        neighbours(sx, sy, function(nx, ny, ni)
          if not shown[ni] then stack[#stack + 1] = {nx, ny} end
        end)
      end
    end
  end
end

local function checkWin()
  local hidden = 0
  for i = 1, W * H do
    if not shown[i] and not mine[i] then hidden = hidden + 1 end
  end
  if hidden == 0 then
    won = true
    alive = false
    message = "cleared it. r restarts, q quits"
  end
end

local function cellText(x, y)
  local i = idx(x, y)
  if not alive and mine[i] and not flag[i] then
    return COLOUR[1] .. "*"
  elseif flag[i] then
    return COLOUR[3] .. "F"
  elseif not shown[i] then
    return COLOUR[7] .. "."
  else
    local n = count(x, y)
    if n == 0 then return COLOUR[0] .. " " end
    return NUMCOL[n] .. n
  end
end

local function draw()
  local out = {at(1, 1)}
  out[#out + 1] = COLOUR[6] .. "minesweeper" .. RESET .. "   mines left: " .. flagsLeft() .. EOL
  out[#out + 1] = at(2, 1) .. EOL
  for y = 1, H do
    local row = {at(y + 2, 1)}
    for x = 1, W do
      local marker = " "
      if x == cx and y == cy then marker = COLOUR[2] .. ">" end
      row[#row + 1] = marker .. cellText(x, y) .. RESET
    end
    row[#row + 1] = EOL
    out[#out + 1] = table.concat(row)
  end
  out[#out + 1] = at(H + 3, 1) .. EOL
  out[#out + 1] = at(H + 4, 1) .. message .. EOL
  io.write(table.concat(out))
  io.stdout:flush()
end

local function toggleFlag()
  local i = idx(cx, cy)
  if not shown[i] then flag[i] = not flag[i] end
end

-- one key, or one typed command when there's no terminal
local function readKey(raw)
  if raw then
    local c = io.read(1)
    if c == nil then return "q" end
    if c == ESC then
      local a = io.read(1)
      local b = io.read(1)
      if a == "[" then
        if b == "A" then return "up" end
        if b == "B" then return "down" end
        if b == "C" then return "right" end
        if b == "D" then return "left" end
      end
      return ""
    end
    return c
  end
  io.write("move (w/a/s/d), space, f, r, q > ")
  io.stdout:flush()
  local line = io.read("l")
  if line == nil then return "q" end
  return line:sub(1, 1)
end

math.randomseed((os.time() or 0) + (sys and sys.ms and sys.ms() or 0))
reset()

local raw = false
if sys and sys.raw then raw = sys.raw(true) end
if not raw then
  message = "no terminal: type w a s d, space, f, r, q"
end

io.write(CLEAR)
while true do
  draw()
  local k = readKey(raw)
  if k == "q" or k == "Q" then
    break
  elseif k == "r" or k == "R" then
    reset()
  elseif alive then
    if k == "up" or k == "w" then cy = cy > 1 and cy - 1 or cy
    elseif k == "down" or k == "s" then cy = cy < H and cy + 1 or cy
    elseif k == "left" or k == "a" then cx = cx > 1 and cx - 1 or cx
    elseif k == "right" or k == "d" then cx = cx < W and cx + 1 or cx
    elseif k == " " or k == "\n" or k == "\r" then
      dig(cx, cy)
      if alive then checkWin() end
    elseif k == "f" or k == "F" then
      toggleFlag()
    end
  end
end

if raw then sys.raw(false) end
io.write(CLEAR .. at(1, 1) .. RESET)
io.stdout:flush()
