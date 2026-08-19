#define EIDSP_QUANTIZE_FILTERBANK   0

#define EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW 4

#include <PDM.h>
#include <IPS_-_projekat_1_inferencing.h>
#include <string.h>
#include <Arduino_APDS9960.h>
#include <Arduino_LSM9DS1.h>

/** Audio buffers, pointers and selectors */
typedef struct {
    signed short *buffers[2];
    unsigned char buf_select;
    unsigned char buf_ready;
    unsigned int buf_count;
    unsigned int n_samples;
} inference_t;

static inference_t inference;
static bool record_ready = false;
static signed short *sampleBuffer;
static bool debug_nn = false;
static int print_results = -(EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);

bool blinking = false;
bool ledState = false;

unsigned long lastBlinkTime = 0;
const unsigned long blinkInterval = 500;

const int LIGHT_THRESHOLD = 120;

// IMU reading interval
unsigned long lastIMURead = 0;
const unsigned long IMU_INTERVAL = 100;   // 100 ms


/**
 * @brief Arduino setup function
 */
void setup()
{
    Serial.begin(115200);

    while (!Serial);

    Serial.println("Edge Impulse Inferencing Demo");

    // Edge Impulse settings
    ei_printf("Inferencing settings:\n");
    ei_printf("\tInterval: %.2f ms.\n",
        (float)EI_CLASSIFIER_INTERVAL_MS);

    ei_printf("\tFrame size: %d\n",
        EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE);

    ei_printf("\tSample length: %d ms.\n",
        EI_CLASSIFIER_RAW_SAMPLE_COUNT / 16);

    ei_printf("\tNo. of classes: %d\n",
        sizeof(ei_classifier_inferencing_categories) /
        sizeof(ei_classifier_inferencing_categories[0]));


    // ---------------------------------------------------------
    // LED SETUP
    // ---------------------------------------------------------

    pinMode(LEDB, OUTPUT);
    digitalWrite(LEDB, HIGH); // Blue LED OFF

    pinMode(LEDR, OUTPUT);
    digitalWrite(LEDR, HIGH); // Red LED OFF


    // ---------------------------------------------------------
    // APDS9960 LIGHT SENSOR
    // ---------------------------------------------------------

    if (!APDS.begin()) {
        Serial.println("Failed to initialize APDS9960!");
        while (1);
    }

    Serial.println("APDS9960 initialized.");


    // ---------------------------------------------------------
    // LSM9DS1 IMU
    // ---------------------------------------------------------

    if (!IMU.begin()) {
        Serial.println("Failed to initialize LSM9DS1!");
        while (1);
    }

    Serial.println("LSM9DS1 IMU initialized.");


    // ---------------------------------------------------------
    // EDGE IMPULSE
    // ---------------------------------------------------------

    run_classifier_init();

    if (microphone_inference_start(
            EI_CLASSIFIER_SLICE_SIZE) == false) {

        ei_printf(
            "ERR: Could not allocate audio buffer "
            "(size %d), this could be due to the window "
            "length of your model\r\n",
            EI_CLASSIFIER_RAW_SAMPLE_COUNT
        );

        return;
    }
}


/**
 * @brief Arduino main function
 */
void loop()
{
    // =========================================================
    // MICROPHONE / EDGE IMPULSE
    // =========================================================

    bool m = microphone_inference_record();

    if (!m) {
        ei_printf(
            "ERR: Failed to record audio...\n"
        );

        return;
    }

    signal_t signal;

    signal.total_length =
        EI_CLASSIFIER_SLICE_SIZE;

    signal.get_data =
        &microphone_audio_signal_get_data;

    ei_impulse_result_t result = {0};

    EI_IMPULSE_ERROR r =
        run_classifier_continuous(
            &signal,
            &result,
            debug_nn
        );

    if (r != EI_IMPULSE_OK) {
        ei_printf(
            "ERR: Failed to run classifier (%d)\n",
            r
        );

        return;
    }


    // =========================================================
    // EDGE IMPULSE PREDICTIONS
    // =========================================================

    if (++print_results >=
        EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW) {

        ei_printf("Predictions ");

        ei_printf(
            "(DSP: %d ms., Classification: %d ms., Anomaly: %d ms.)",
            result.timing.dsp,
            result.timing.classification,
            result.timing.anomaly
        );

        ei_printf(": \n");


        for (size_t ix = 0;
             ix < EI_CLASSIFIER_LABEL_COUNT;
             ix++) {

            const char *label =
                result.classification[ix].label;

            float value =
                result.classification[ix].value;


            ei_printf(
                "    %s: %.5f\n",
                label,
                value
            );


            // =================================================
            // VOICE COMMANDS
            // =================================================

            if (value > 0.90f) {

                // -----------------------------
                // LETS_START
                // -----------------------------

                if (strcmp(label, "Lets_start") == 0) {

                    blinking = true;

                    Serial.println(
                        "START command detected"
                    );
                }


                // -----------------------------
                // FINISH
                // -----------------------------

                if (strcmp(label, "Finish") == 0) {

                    blinking = false;

                    ledState = false;

                    digitalWrite(
                        LEDB,
                        HIGH
                    );

                    digitalWrite(
                        LEDR,
                        HIGH
                    );

                    Serial.println(
                        "FINISH command detected"
                    );
                }
            }
        }


#if EI_CLASSIFIER_HAS_ANOMALY == 1

        ei_printf(
            "    anomaly score: %.3f\n",
            result.anomaly
        );

#endif

        print_results = 0;
    }


    // =========================================================
    // SENSOR READINGS
    // =========================================================
    // Do these AFTER the audio inference.
    // Read them only once every 500 ms.

    static unsigned long lastSensorRead = 0;

    if (millis() - lastSensorRead >= 500) {

        lastSensorRead = millis();


        // =====================================================
        // BLUE LED BLINKING
        // =====================================================

        if (blinking) {

            if (millis() - lastBlinkTime >= blinkInterval) {

                lastBlinkTime = millis();

                ledState = !ledState;

                if (ledState) {
                    digitalWrite(LEDB, LOW);
                }
                else {
                    digitalWrite(LEDB, HIGH);
                }
            }
        }
        else {
            digitalWrite(LEDB, HIGH);
            ledState = false;
        }


        // =====================================================
        // LIGHT SENSOR
        // =====================================================

        if (blinking) {

            if (APDS.colorAvailable()) {

                int r, g, b;

                APDS.readColor(r, g, b);

                int light =
                    (r + g + b) / 3;

                if (light > LIGHT_THRESHOLD) {

                    digitalWrite(
                        LEDR,
                        LOW
                    );
                }
                else {

                    digitalWrite(
                        LEDR,
                        HIGH
                    );
                }

                Serial.print("Light: ");
                Serial.println(light);
            }
        }
        else {

            digitalWrite(
                LEDR,
                HIGH
            );
        }


        // =====================================================
        // ACCELEROMETER
        // =====================================================

        if(blinking)
        {
            if (IMU.accelerationAvailable()) {

                float x, y, z;

                IMU.readAcceleration(
                    x,
                    y,
                    z
                );

                float totalAcceleration =
                    sqrt(
                        x * x +
                        y * y +
                        z * z
                    );

                Serial.print("X: ");
                Serial.print(x, 3);

                Serial.print(" Y: ");
                Serial.print(y, 3);

                Serial.print(" Z: ");
                Serial.print(z, 3);

                Serial.print(" Total: ");
                Serial.println(
                    totalAcceleration,
                    3
                );
            }
        }
    }
}


/**
 * @brief PDM buffer full callback
 */
static void pdm_data_ready_inference_callback(void)
{
    int bytesAvailable = PDM.available();

    int bytesRead =
        PDM.read(
            (char *)&sampleBuffer[0],
            bytesAvailable
        );


    if (record_ready == true) {

        for (int i = 0;
             i < bytesRead >> 1;
             i++) {

            inference.buffers[
                inference.buf_select
            ][inference.buf_count++] =
                sampleBuffer[i];


            if (inference.buf_count >=
                inference.n_samples) {

                inference.buf_select ^= 1;

                inference.buf_count = 0;

                inference.buf_ready = 1;
            }
        }
    }
}


/**
 * @brief Initialize microphone inference
 */
static bool microphone_inference_start(
    uint32_t n_samples
)
{
    inference.buffers[0] =
        (signed short *)malloc(
            n_samples *
            sizeof(signed short)
        );


    if (inference.buffers[0] == NULL) {
        return false;
    }


    inference.buffers[1] =
        (signed short *)malloc(
            n_samples *
            sizeof(signed short)
        );


    if (inference.buffers[1] == NULL) {

        free(inference.buffers[0]);

        return false;
    }


    sampleBuffer =
        (signed short *)malloc(
            (n_samples >> 1) *
            sizeof(signed short)
        );


    if (sampleBuffer == NULL) {

        free(inference.buffers[0]);
        free(inference.buffers[1]);

        return false;
    }


    inference.buf_select = 0;
    inference.buf_count = 0;
    inference.n_samples = n_samples;
    inference.buf_ready = 0;


    PDM.onReceive(
        &pdm_data_ready_inference_callback
    );


    PDM.setBufferSize(
        (n_samples >> 1) *
        sizeof(int16_t)
    );


    if (!PDM.begin(
        1,
        EI_CLASSIFIER_FREQUENCY
    )) {

        ei_printf(
            "Failed to start PDM!"
        );
    }


    PDM.setGain(127);

    record_ready = true;

    return true;
}


/**
 * @brief Wait on new audio data
 */
static bool microphone_inference_record(void)
{
    bool ret = true;


    if (inference.buf_ready == 1) {

        ei_printf(
            "Error sample buffer overrun. "
            "Decrease the number of slices per model window "
            "(EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW)\n"
        );

        ret = false;
    }


    while (inference.buf_ready == 0) {

        delay(1);
    }


    inference.buf_ready = 0;

    return ret;
}


/**
 * Get raw audio signal data
 */
static int microphone_audio_signal_get_data(
    size_t offset,
    size_t length,
    float *out_ptr
)
{
    numpy::int16_to_float(
        &inference.buffers[
            inference.buf_select ^ 1
        ][offset],

        out_ptr,

        length
    );

    return 0;
}


/**
 * @brief Stop PDM and release buffers
 */
static void microphone_inference_end(void)
{
    PDM.end();

    free(inference.buffers[0]);
    free(inference.buffers[1]);
    free(sampleBuffer);
}


#if !defined(EI_CLASSIFIER_SENSOR) || \
    EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_MICROPHONE

#error "Invalid model for current sensor."

#endif