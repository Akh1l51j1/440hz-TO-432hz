# 🎵 Real-Time 432 Hz Audio Converter

A lightweight, zero-latency Python application that intercepts your system's audio (e.g., Spotify, YouTube, Apple Music) and converts it from standard 440 Hz tuning to **432 Hz** in real-time.

Unlike traditional pitch-shifting methods that suffer from stuttering or block-boundary artifacts (crackling), this tool uses a **continuous ring buffer with cubic Hermite interpolation**. This means zero audio glitches, zero crackling, and a smooth, unbroken listening experience.

---

## 🎧 What it Does

- Captures audio output from any Windows application (using WASAPI).
- Pitch-shifts the audio down by approximately -0.32 semitones (440 Hz → 432 Hz).
- Outputs the converted audio directly to your physical speakers or Bluetooth headphones.
- Uses advanced ring-buffer processing to ensure no pops or clicks at block boundaries.

---

## 🛠️ Requirements & Setup

This guide is for Windows users, as it relies on Windows WASAPI and Virtual Audio Cables for routing.

### 1. Install Virtual Audio Cable
To intercept the audio from Spotify or other apps before it hits your speakers, you need a virtual audio cable.
1. Download and install **[VB-Cable Virtual Audio Device](https://vb-audio.com/Cable/)** (it's free).
2. Restart your computer if prompted.

### 2. Route Your Application's Audio
1. Open Windows **Settings** > **System** > **Sound**.
2. Scroll down to **Volume mixer**.
3. Find the app you want to convert (e.g., Spotify). Play some music so it shows up in the list.
4. Click the arrow next to the app and change the **Output device** to **`CABLE Input (VB-Audio Virtual Cable)`**.
*(Note: You won't hear anything from the app yet—that's expected!)*

### 3. Install Python Dependencies
Make sure you have Python installed. Then, open your terminal/command prompt and run:
```bash
pip install sounddevice numpy
```

---

## 🚀 How to Run

1. Clone or download this repository.
2. Run the main converter script:
   ```bash
   python 432_converter.py
   ```
3. The script will automatically detect the `CABLE Output` as its input source.
4. It will list all available WASAPI output devices. **Enter the number corresponding to your actual Speakers or Headphones** (e.g., `Speakers (Realtek(R) Audio)` or your Bluetooth Headphones).
   - *Do NOT select `CABLE Input` as the output, or you will create an infinite loop of silence!*

**Boom!** You should now hear your music playing at 432 Hz through your selected device. Press `Ctrl+C` in the terminal to stop the stream.

---

## 🛟 Troubleshooting

- **No sound coming through?**
  Double-check your Windows Volume Mixer. The app (Spotify) MUST output to `CABLE Input`, and the Python script MUST output to your physical hardware (Speakers/Headphones).
- **"Invalid device" or "Exclusive mode" errors?**
  Go to Windows Sound settings > More Sound Settings. Right-click your device > Properties > Advanced tab. **Uncheck** "Allow applications to take exclusive control of this device" for both the Virtual Cable and your Speakers/Headphones.
- **Can't find my Bluetooth headphones in the list?**
  Ensure they are connected to Windows first. You can run the included `list_devices.py` script to see a full list of recognized audio devices:
  ```bash
  python list_devices.py
  ```

---

## 🧠 How it Works (For the Nerds)
Most real-time pitch shifters process audio in chunks (blocks). When you pitch-shift independent blocks, the end of Block 1 doesn't match the start of Block 2, causing an audible "click" or "crackle" every few milliseconds.

This converter solves that by using a **Continuous Ring Buffer**:
1. Incoming audio is written to a large circular buffer (262,144 samples).
2. A fractional read pointer glides through this buffer at exactly `432 / 440` speed.
3. Because the read pointer never resets and uses **Cubic Hermite Interpolation** (a 4-point spline), the output stream is 100% continuous, mathematical perfection. Zero block edges = zero crackle.


## 🧠 Why 432 Hz? The Science Behind the Pitch

While the internet is filled with mystical claims about 432 Hz, this project is built on the foundation of **peer-reviewed clinical research**. 

Shifting music down by just 1.8% (from the 440 Hz global standard to 432 Hz) has been clinically shown to produce statistically significant, measurable physiological benefits. For developers, students, and professionals who spend hours in deep focus, this real-time converter acts as a tool to manage cognitive load, reduce acoustic fatigue, and sustain mental endurance.

Here is what the clinical data says about the 432 Hz tuning:

### 1. Measurable Drop in Heart Rate and Blood Pressure
A 2019 double-blind cross-over pilot study (Calamassi & Pomponi) found that patients listening to music tuned to 432 Hz experienced a more significant decrease in their heart rate compared to those listening to the exact same tracks at 440 Hz. 

A subsequent 2022 randomized, controlled study published in *Acta Biomedica* tested emergency room nurses during the height of the COVID-19 pandemic. The nurses who listened to 432 Hz music during their breaks showed a statistically significant reduction in both respiratory rate and systolic blood pressure compared to the 440 Hz control group.

### 2. Decrease in Stress Hormones (Cortisol)
The calming effect of 432 Hz is not just psychological; it is chemical. A 2020 randomized clinical trial (Aravena et al.) tested patients' salivary cortisol levels (the body's primary stress hormone) while under extreme stress. The group listening to music tuned to 432 Hz showed a measurable decrease in cortisol levels, proving that the tuning physically triggers the parasympathetic nervous system (your "rest and digest" mode).

### 3. Brainwave Entrainment & Acoustic Fatigue
Standard 440 Hz music pushes high-end frequencies directly into the most sensitive part of the human ear canal, which can cause acoustic fatigue during long listening sessions. 
* By dropping the pitch by 8 Hz, this converter mathematically rounds off sharp, harsh frequencies, creating a warmer sound profile.
* This softer acoustic anchor encourages **Brainwave Entrainment**, gently nudging the brain's electrical activity away from the stressed, highly alert **Beta state** and into the calm, highly focused **Alpha state** (often referred to as the "Flow State").

> **The Verdict:** 432 Hz is not magic, but it is acoustic science. It is clinically proven to lower physical stress markers and reduce auditory fatigue. If you need to lock in and concentrate for hours without burning out, running your system audio through this converter can help keep your nervous system relaxed and your mind clear.

CUREENTLY NO FRONTEND FOR THIS PROJECT!!