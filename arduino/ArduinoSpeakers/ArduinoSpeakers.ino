#include "HL1606strip.h"

// Light defines
#define STRIP_D    51
#define STRIP_C    52
#define STRIP_L    10
#define STRIP_LEN  100

#define LSIZE 36
#define RSIZE 36
#define CSIZE 28

// Command Defines
#define MAX_COMMAND      100
#define MAX_VALUE        255
#define DELIMITERS       ","

HL1606strip strip = HL1606strip(STRIP_D, STRIP_L, STRIP_C, STRIP_LEN);

int lights[STRIP_LEN+1];
uint8_t colours[] = {BLACK,RED,YELLOW,GREEN,TEAL,BLUE,VIOLET,WHITE};
bool reverse = false;

class Command {
  public:
    uint8_t lcolour;
    uint8_t lsize;
    uint8_t rcolour;
    uint8_t rsize;
    uint8_t ccolour;
    uint8_t csize;
    bool updated;
    int args[6];
  
  bool getCommand(char* command) {
    bool fail = false;
    args[0] = atoi(strtok(command, DELIMITERS));
    args[1] = atoi(strtok(NULL, DELIMITERS));
    args[2] = atoi(strtok(NULL, DELIMITERS));
    args[3] = atoi(strtok(NULL, DELIMITERS));
    args[4] = atoi(strtok(NULL, DELIMITERS));
    args[5] = atoi(strtok(NULL, DELIMITERS));
    //Serial.println(args[0]);
    //Serial.println(args[1]);
    //Serial.println(args[2]);
    //Serial.println(args[3]);

    if (args[0] < 0 || args[0] > LSIZE) {
      fail = true;
      //Serial.println("Invalid l size");
    } else {
      lsize = args[0];
    }
    if (args[1] < 0 || args[1] > 7) {
      fail = true;
      //Serial.println("Invalid l colour");
    } else {
      lcolour = args[1];
    }
    if (args[2] < 0 || args[2] > RSIZE) {
      fail = true;
      //Serial.println("Invalid r size");
    } else {
      rsize = args[2];
    }
    if (args[3] < 0 || args[3] > 7) {
      fail = true;
      //Serial.println("Invalid r colour");
    } else {
      rcolour = args[3];
    }

    if (args[4] < 0 || args[4] > CSIZE) {
      fail = true;
      //Serial.println("Invalid r size");
    } else {
      csize = args[4];
    }
    if (args[5] < 0 || args[5] > 7) {
      fail = true;
      //Serial.println("Invalid r colour");
    } else {
      ccolour = args[5];
    }
    
    if (!fail) {
      updated = true; 
    }
    return true;
  }
};

Command cmd;

void update() {
  if (cmd.updated) {
    cmd.updated = false;
    solidColour(); 
  }
}

String inputString = "";         // a string to hold incoming data
boolean stringComplete = false;  // whether the string is complete
char command[MAX_COMMAND];

void setup() {
  // initialize serial:
  Serial.begin(115200);
  Serial.println("Hello!");
  // reserve 200 bytes for the inputString:
  inputString.reserve(200);
  cmd.getCommand("36,2,36,3,28,4");
  update();
  delay(1000);
  cmd.getCommand("36,0,36,0,28,0");
  update();
}

void loop() {
  // print the string when a newline arrives:
  if (stringComplete) {
    inputString.toCharArray(command,inputString.length());
    //Serial.println(command); 
    // clear the string:
    inputString = "";
    stringComplete = false;
    cmd.getCommand(command);
    //Serial.println(cmd.getCommand(command));
  }
  update();
  delay(2);
  /*strip.setLEDcolor(0, BLUE);
  strip.setLEDcolor(99, RED);
  strip.writeStrip();
  delay(1000);*/
}

/*
  SerialEvent occurs whenever a new data comes in the
 hardware serial RX.  This routine is run between each
 time loop() runs, so using delay inside loop can delay
 response.  Multiple bytes of data may be available.
 */
void serialEvent() {
  while (Serial.available()) {
    // get the new byte:
    char inChar = (char)Serial.read(); 
    // add it to the inputString:
    inputString += inChar;
    // if the incoming character is a newline, set a flag
    // so the main loop can do something about it:
    if (inChar == '\n') {
      stringComplete = true;
    } 
  }
}

// fill with colour
void solidColour() {
  for (uint8_t i=0; i < strip.numLEDs(); i++) {
      strip.setLEDcolor(i, BLACK);
  }
  for (uint8_t i=0; i < cmd.lsize; ++i) {
    strip.setLEDcolor(i, cmd.lcolour);
  }
  for (uint8_t i=LSIZE; i < cmd.rsize+LSIZE; ++i) {
    strip.setLEDcolor(i, cmd.rcolour);
  }
  for (uint8_t i=LSIZE+RSIZE; i < cmd.csize+LSIZE+RSIZE; ++i) {
    strip.setLEDcolor(i, cmd.ccolour);
  }
  strip.writeStrip();
}
