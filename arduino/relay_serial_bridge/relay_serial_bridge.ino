const unsigned long SERIAL_BAUD = 9600;
const int RELAY_COUNT = 8;
const int RELAY_PINS[RELAY_COUNT] = {2, 3, 4, 5, 6, 7, 8, 9};

String inputBuffer;

void setup() {
  Serial.begin(SERIAL_BAUD);
  inputBuffer.reserve(48);

  for (int i = 0; i < RELAY_COUNT; ++i) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);
  }

  Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleCommand(inputBuffer);
      inputBuffer = "";
      continue;
    }
    inputBuffer += c;
    if (inputBuffer.length() > 47) {
      inputBuffer = "";
      Serial.println("ERR COMMAND TOO LONG");
    }
  }
}

void handleCommand(String command) {
  command.trim();
  if (command.length() == 0) {
    return;
  }

  int firstSpace = command.indexOf(' ');
  int secondSpace = command.indexOf(' ', firstSpace + 1);
  if (firstSpace < 0 || secondSpace < 0) {
    Serial.println("ERR BAD FORMAT");
    return;
  }

  String prefix = command.substring(0, firstSpace);
  String relayText = command.substring(firstSpace + 1, secondSpace);
  String stateText = command.substring(secondSpace + 1);

  prefix.trim();
  relayText.trim();
  stateText.trim();
  stateText.toUpperCase();

  if (prefix != "ZONE") {
    Serial.println("ERR UNKNOWN COMMAND");
    return;
  }

  int relayId = relayText.toInt();
  if (relayId < 1 || relayId > RELAY_COUNT) {
    Serial.println("ERR BAD RELAY");
    return;
  }

  bool isOn;
  if (stateText == "ON") {
    isOn = true;
  } else if (stateText == "OFF") {
    isOn = false;
  } else {
    Serial.println("ERR BAD STATE");
    return;
  }

  // Active-high relay test output.
  // If your real relay board is active-low later, invert this line.
  digitalWrite(RELAY_PINS[relayId - 1], isOn ? HIGH : LOW);

  Serial.print("ACK ");
  Serial.print(relayId);
  Serial.print(' ');
  Serial.println(isOn ? "ON" : "OFF");
}
