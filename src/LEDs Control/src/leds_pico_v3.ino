#include <Adafruit_NeoPixel.h>

#define PIN_FITA       15
#define NUMPIXELS      180

const int BRILHO_MAXIMO = 60;

int serpLen = 0;
bool serpGrowing = true;
uint16_t serpHue = 0;

Adafruit_NeoPixel fita = Adafruit_NeoPixel(NUMPIXELS, PIN_FITA, NEO_GRB + NEO_KHZ800);

int efeitoAtual = 0;
const int totalEfeitos = 20;
unsigned long tempoAnteriorFita = 0;
int intervaloFita = 25;

int posicaoAtual = 0;
int direcao = 1;
int fase = 0;
uint16_t hueGlobal = 0;
uint16_t corAlvo = 0;

// --- Handshake & Ping ---
bool handshakeFeito = false;
int sequenceNumber = 0;
unsigned long tempoAnteriorPing = 0;
const long intervaloPing = 1000;

// ==========================================
// SISTEMA DE FADE/TRANSIÇÃO
// ==========================================
// Guarda o snapshot dos LEDs no momento da mudança
uint8_t fadeSnapshot[NUMPIXELS][3];

// Estados da máquina de transição
enum EstadoFade { NORMAL, FADE_OUT, FADE_IN };
EstadoFade estadoFade = NORMAL;

float fadeValor = 1.0;          // 1.0 = cheio, 0.0 = apagado
const float FADE_STEP = 0.07;   // velocidade do fade (por frame a 25ms ≈ ~350ms total)
int efeitoProximo = -1;         // efeito para o qual vamos transitar

// Captura o estado atual da fita para o snapshot
void tirarSnapshot() {
  for (int i = 0; i < NUMPIXELS; i++) {
    uint32_t c = fita.getPixelColor(i);
    fadeSnapshot[i][0] = (c >> 16) & 0xFF; // R
    fadeSnapshot[i][1] = (c >>  8) & 0xFF; // G
    fadeSnapshot[i][2] =  c        & 0xFF; // B
  }
}

// Aplica o snapshot com um multiplicador de brilho (0.0 a 1.0)
void aplicarSnapshotComFade(float mult) {
  for (int i = 0; i < NUMPIXELS; i++) {
    fita.setPixelColor(i, fita.Color(
      fadeSnapshot[i][0] * mult,
      fadeSnapshot[i][1] * mult,
      fadeSnapshot[i][2] * mult
    ));
  }
}

// Multiplica o brilho de todos os LEDs atuais por um fator
void aplicarBrilhoGlobal(float mult) {
  for (int i = 0; i < NUMPIXELS; i++) {
    uint32_t c = fita.getPixelColor(i);
    int r = ((c >> 16) & 0xFF) * mult;
    int g = ((c >>  8) & 0xFF) * mult;
    int b = ( c        & 0xFF) * mult;
    fita.setPixelColor(i, fita.Color(
      constrain(r, 0, 255),
      constrain(g, 0, 255),
      constrain(b, 0, 255)
    ));
  }
}

// Inicia uma transição para o próximo efeito
void iniciarTransicao(int novoEfeito) {
  tirarSnapshot();       // guarda o frame atual
  efeitoProximo = novoEfeito;
  fadeValor = 1.0;
  estadoFade = FADE_OUT;
}

void resetEfeito() {
  posicaoAtual = 0;
  direcao = 1;
  fase = 0;
  serpLen = 0;
  serpGrowing = true;
  corAlvo = random(65536);
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  fita.begin();
  fita.setBrightness(BRILHO_MAXIMO);
  fita.show();
}

void piscarLED() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(80);
  digitalWrite(LED_BUILTIN, LOW);
}

void correrEfeito(int efeito, unsigned long tempo) {
  switch(efeito) {
    case 0:  arcoIrisFluido();        break;
    case 1:  confetes();              break;
    case 2:  scannerCylon();          break;
    case 3:  respiracaoOceano(tempo); break;
    case 4:  auroraBorealis(tempo);   break;
    case 5:  cometaArcoIris();        break;
    case 6:  plasmaQuantico(tempo);   break;
    case 7:  scannerDuplo();          break;
    case 8:  vagalumes();             break;
    case 9:  serpenteCromatica();     break;
    case 10: explosaoEstrela();       break;
    case 11: preenchimentoSurpresa(); break;
    case 12: fogo();                  break;
    case 13: agua(tempo);             break;
    case 14: matrix();                break;
    case 15: lavarLava(tempo);        break;
    case 16: tempestade(tempo);       break;
    case 17: galaxia();               break;
    case 18: neon();                  break;
    case 19: neveiro(tempo);          break;
  }
}

void loop() {
  unsigned long tempoAtual = millis();

  // 1. LER COMANDOS DO PC
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("INT:")) {
      sequenceNumber = cmd.substring(4).toInt();
      Serial.print("received:");
      Serial.println(sequenceNumber);
      piscarLED();
      handshakeFeito = true;

    } else if (cmd == "R") {
      int proximo = (efeitoAtual + 1) % totalEfeitos;
      iniciarTransicao(proximo);
      piscarLED();
      Serial.print("ok:R:");
      Serial.println(proximo);

    } else if (cmd == "L") {
      int proximo = (efeitoAtual - 1 + totalEfeitos) % totalEfeitos;
      iniciarTransicao(proximo);
      piscarLED();
      Serial.print("ok:L:");
      Serial.println(proximo);

    } else if (cmd == "PING") {
      Serial.println("PONG");

    } else if (cmd.startsWith("FX:")) {
      int fxId = cmd.substring(3).toInt();
      if (fxId >= 0 && fxId < totalEfeitos) {
        iniciarTransicao(fxId);
        efeitoAtual = fxId;
        piscarLED();
        Serial.print("ok:FX:");
        Serial.println(fxId);
      } else {
        Serial.println("err:FX:out_of_range");
      }
    }
  }

  // 2. PING AUTOMÁTICO
  if (handshakeFeito && tempoAtual - tempoAnteriorPing >= intervaloPing) {
    tempoAnteriorPing = tempoAtual;
    Serial.print("alive:");
    Serial.println(efeitoAtual);
  }

  // 3. FRAME — com máquina de estados de fade
  if (tempoAtual - tempoAnteriorFita >= intervaloFita) {
    tempoAnteriorFita = tempoAtual;

    if (estadoFade == FADE_OUT) {
      // Mostra o snapshot a escurecer
      fadeValor -= FADE_STEP;
      if (fadeValor <= 0.0) {
        fadeValor = 0.0;
        // Chegou a 0 → muda de efeito e começa fade in
        efeitoAtual = efeitoProximo;
        resetEfeito();
        // Gera o primeiro frame do novo efeito (ainda invisível)
        correrEfeito(efeitoAtual, tempoAtual);
        tirarSnapshot(); // snapshot do novo efeito
        estadoFade = FADE_IN;
      } else {
        aplicarSnapshotComFade(fadeValor);
      }

    } else if (estadoFade == FADE_IN) {
      // Renderiza o novo efeito e aplica fade in
      correrEfeito(efeitoAtual, tempoAtual);
      fadeValor += FADE_STEP;
      if (fadeValor >= 1.0) {
        fadeValor = 1.0;
        estadoFade = NORMAL;
      } else {
        aplicarBrilhoGlobal(fadeValor);
      }

    } else {
      // NORMAL: corre o efeito sem fade
      correrEfeito(efeitoAtual, tempoAtual);
    }

    fita.show();
  }
}

// ==========================================
// FUNÇÃO AUXILIAR
// ==========================================
void escurecerFita(uint8_t taxa) {
  for(int i = 0; i < NUMPIXELS; i++) {
    uint32_t cor = fita.getPixelColor(i);
    int r = (cor >> 16) & 0xFF;
    int g = (cor >>  8) & 0xFF;
    int b = cor & 0xFF;
    r = (r - taxa > 0) ? r - taxa : 0;
    g = (g - taxa > 0) ? g - taxa : 0;
    b = (b - taxa > 0) ? b - taxa : 0;
    fita.setPixelColor(i, fita.Color(r, g, b));
  }
}

// ==========================================
// EFEITOS (0–19)
// ==========================================
void arcoIrisFluido() {
  hueGlobal += 150;
  for(int i = 0; i < NUMPIXELS; i++) {
    int pixelHue = hueGlobal + (i * 65536L / NUMPIXELS);
    fita.setPixelColor(i, fita.gamma32(fita.ColorHSV(pixelHue)));
  }
}
void confetes() {
  escurecerFita(15);
  if (random(10) > 4)
    fita.setPixelColor(random(NUMPIXELS), fita.ColorHSV(random(65536)));
}
void scannerCylon() {
  escurecerFita(25);
  fita.setPixelColor(posicaoAtual, fita.Color(255, 0, 0));
  posicaoAtual += direcao;
  if (posicaoAtual >= NUMPIXELS - 1 || posicaoAtual <= 0) direcao = -direcao;
}
void respiracaoOceano(unsigned long tempo) {
  float onda = (exp(sin(tempo / 1500.0 * PI)) - 0.36787944) * 108.0;
  int brilhoLocal = map(onda, 0, 255, 0, 255);
  uint32_t cor = fita.Color(0, brilhoLocal, brilhoLocal);
  for(int i = 0; i < NUMPIXELS; i++) fita.setPixelColor(i, cor);
}
void auroraBorealis(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++) {
    float x = (float)i / NUMPIXELS;
    float onda1 = sin(x * 6.0 + tempo / 800.0) * 0.5 + 0.5;
    float onda2 = sin(x * 3.0 - tempo / 1200.0) * 0.5 + 0.5;
    float mix = onda1 * onda2;
    int verde  = constrain(mix * 200 * sin(x * 2 + tempo / 2000.0), 0, 255);
    int roxo   = constrain(mix * 180 * sin(x * 3 - tempo / 1500.0 + 2), 0, 255);
    int brilho = constrain(mix * 255, 0, 255);
    fita.setPixelColor(i, fita.Color(
      constrain(roxo * 0.6, 0, 255),
      constrain(verde + roxo * 0.2, 0, 255),
      constrain(brilho * 0.3 + roxo * 0.5, 0, 255)
    ));
  }
}
void cometaArcoIris() {
  escurecerFita(20);
  fita.setPixelColor(posicaoAtual, fita.ColorHSV(hueGlobal));
  hueGlobal += 1000;
  posicaoAtual++;
  if (posicaoAtual >= NUMPIXELS) posicaoAtual = 0;
}
void plasmaQuantico(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++) {
    float x = (float)i / NUMPIXELS;
    float v = sin(x * 10 + tempo / 300.0)
            + sin(x * 7  - tempo / 250.0)
            + sin((x + tempo / 3000.0) * 5);
    float norm = (v / 3.0 + 1.0) / 2.0;
    uint16_t h = (uint16_t)(norm * 65535) + (tempo / 33);
    fita.setPixelColor(i, fita.gamma32(fita.ColorHSV(h, 255, 230)));
  }
}
void scannerDuplo() {
  escurecerFita(30);
  fita.setPixelColor(posicaoAtual, fita.Color(0, 255, 255));
  fita.setPixelColor(NUMPIXELS - 1 - posicaoAtual, fita.Color(255, 0, 255));
  posicaoAtual += direcao;
  if (posicaoAtual >= NUMPIXELS - 1 || posicaoAtual <= 0) direcao = -direcao;
}
void vagalumes() {
  escurecerFita(5);
  if (random(100) > 90)
    fita.setPixelColor(random(NUMPIXELS), fita.Color(150, 255, 0));
}
void serpenteCromatica() {
  fita.clear();
  if (serpGrowing) { serpLen++; if (serpLen >= 60) serpGrowing = false; }
  else             { serpLen--; if (serpLen <= 1)  { serpGrowing = true; serpHue += 8000; direcao = -direcao; } }
  posicaoAtual += direcao;
  posicaoAtual = constrain(posicaoAtual, 0, NUMPIXELS - 1);
  if (posicaoAtual >= NUMPIXELS - 1 || posicaoAtual <= 0) direcao = -direcao;
  for (int j = 0; j < serpLen; j++) {
    int idx = posicaoAtual - direcao * j;
    if (idx < 0 || idx >= NUMPIXELS) continue;
    float bright = 1.0 - (float)j / serpLen;
    fita.setPixelColor(idx, fita.gamma32(fita.ColorHSV(serpHue + j * 300, 255, bright * 255)));
  }
}
void explosaoEstrela() {
  escurecerFita(18);
  int centro = NUMPIXELS / 2;
  uint32_t cor = fita.gamma32(fita.ColorHSV(hueGlobal, 255, 255));
  fita.setPixelColor(centro + posicaoAtual, cor);
  fita.setPixelColor(centro - posicaoAtual, cor);
  posicaoAtual++;
  if (posicaoAtual >= centro) { posicaoAtual = 0; hueGlobal += 9000; }
}
void preenchimentoSurpresa() {
  if (fase == 0) fita.setPixelColor(posicaoAtual, fita.ColorHSV(corAlvo));
  else           fita.setPixelColor(posicaoAtual, fita.Color(0, 0, 0));
  posicaoAtual++;
  if (posicaoAtual >= NUMPIXELS) {
    posicaoAtual = 0;
    fase = !fase;
    if (fase == 0) corAlvo = random(65536);
  }
}
void fogo() {
  for (int i = NUMPIXELS - 1; i > 0; i--) {
    uint32_t c = fita.getPixelColor(i - 1);
    int r = (c >> 16) & 0xFF;
    int g = (c >>  8) & 0xFF;
    int b = c & 0xFF;
    r = constrain(r - random(15), 0, 255);
    g = constrain(g - random(20), 0, 255);
    fita.setPixelColor(i, fita.Color(r, g, b));
  }
  int calor = random(180, 255);
  int verde  = random(0, calor / 3);
  fita.setPixelColor(0, fita.Color(calor, verde, 0));
}
void agua(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++) {
    float onda  = sin((float)i / 8.0 - tempo / 300.0) * 0.5 + 0.5;
    float onda2 = sin((float)i / 5.0 + tempo / 500.0) * 0.3 + 0.3;
    float mix = (onda + onda2) / 2.0;
    int azul  = constrain(mix * 255, 80, 255);
    int verde = constrain(mix * 160, 20, 160);
    fita.setPixelColor(i, fita.Color(0, verde, azul));
  }
}
static uint8_t matrixBrilho[180] = {0};
void matrix() {
  for (int i = 0; i < NUMPIXELS; i++) {
    matrixBrilho[i] = (matrixBrilho[i] > 20) ? matrixBrilho[i] - 20 : 0;
    fita.setPixelColor(i, fita.Color(0, matrixBrilho[i], 0));
  }
  if (random(100) > 60) {
    int pos = random(NUMPIXELS);
    matrixBrilho[pos] = 255;
    fita.setPixelColor(pos, fita.Color(180, 255, 180));
  }
}
void lavarLava(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++) {
    float x = (float)i / NUMPIXELS;
    float v = sin(x * 4.0 + tempo / 1200.0) * sin(x * 7.0 - tempo / 800.0);
    float norm = (v + 1.0) / 2.0;
    int r = constrain(norm * 255 + 80, 0, 255);
    int g = constrain(norm * 80,       0, 255);
    fita.setPixelColor(i, fita.Color(r, g, 0));
  }
}
static unsigned long proximoRelampago = 0;
static int relampagoDuracao = 0;
void tempestade(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++)
    fita.setPixelColor(i, fita.Color(0, 0, 20 + random(5)));
  if (tempo > proximoRelampago) {
    relampagoDuracao = random(2, 6);
    proximoRelampago = tempo + random(500, 3000);
  }
  if (relampagoDuracao > 0) {
    int inicio = random(NUMPIXELS - 20);
    int comprimento = random(10, 30);
    for (int i = inicio; i < min(inicio + comprimento, NUMPIXELS); i++) {
      int brilho = random(180, 255);
      fita.setPixelColor(i, fita.Color(brilho, brilho, 255));
    }
    relampagoDuracao--;
  }
}
static uint8_t estrelas[180] = {0};
static uint8_t estrelasDir[180] = {0};
void galaxia() {
  if (posicaoAtual == 0) {
    for (int i = 0; i < NUMPIXELS; i++) {
      estrelas[i]    = random(0, 80);
      estrelasDir[i] = random(0, 2);
    }
    posicaoAtual = 1;
  }
  for (int i = 0; i < NUMPIXELS; i++) {
    if (estrelasDir[i]) { estrelas[i] += 3; if (estrelas[i] >= 220) estrelasDir[i] = 0; }
    else                { estrelas[i] -= 3; if (estrelas[i] <= 10)  estrelasDir[i] = 1; }
    uint8_t nebula_r = estrelas[i] / 4;
    uint8_t nebula_b = estrelas[i] / 2;
    uint8_t star     = (estrelas[i] > 180) ? estrelas[i] : 0;
    fita.setPixelColor(i, fita.Color(nebula_r + star / 3, star / 4, nebula_b + star / 2));
  }
}
void neon() {
  uint16_t coresNeon[3] = {0, 21845, 43690};
  float pulso = (sin(millis() / 200.0) * 0.4) + 0.6;
  for (int i = 0; i < NUMPIXELS; i++) {
    int bloco = (i / 20 + fase) % 3;
    uint16_t h = coresNeon[bloco] + hueGlobal;
    uint8_t  v = constrain(pulso * 255, 0, 255);
    fita.setPixelColor(i, fita.gamma32(fita.ColorHSV(h, 255, v)));
  }
  if (random(100) > 97) { fase = (fase + 1) % 3; hueGlobal += 2000; }
}
void neveiro(unsigned long tempo) {
  for (int i = 0; i < NUMPIXELS; i++) {
    float x = (float)i / NUMPIXELS;
    float onda = sin(x * 5.0 + tempo / 2000.0) * 0.3
               + sin(x * 9.0 - tempo / 1500.0) * 0.2
               + 0.5;
    int brilho = constrain(onda * 180, 30, 210);
    fita.setPixelColor(i, fita.Color(brilho * 0.85, brilho * 0.92, brilho));
  }
}
