-- blink.lua: blink the LED on GPIO line 0
-- (Pico GP1, physical pin 2)
-- usage: lua blink.lua [times]
local base = "/sys/class/gpio/"

local function write(path, value)
  local f = io.open(path, "w")
  if not f then return false end
  f:write(value)
  f:close()
  return true
end

-- fails harmlessly if already exported
write(base .. "export", "512")
write(base .. "gpio512/direction", "out")

local times = tonumber(arg[1]) or 10
for i = 1, times do
  write(base .. "gpio512/value", "1")
  sys.sleep(0.2)
  write(base .. "gpio512/value", "0")
  sys.sleep(0.2)
end

-- give the line back, or gpioset will say
-- it is busy until reboot
write(base .. "unexport", "512")
print("blinked " .. times .. " times")
