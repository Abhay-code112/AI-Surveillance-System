"""
inference_engine.py — Final Surveillance Pipeline

Two modes:
  - live: Stage 1 only (Violence vs Normal) — fast, reliable
  - video: Full pipeline (Violence + Crime Type) — detailed
"""

import os
import cv2
import torch
import numpy as np
import torch.nn.functional as F
from collections import deque

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

VIOLENCE_MODEL_PATH = os.path.join(MODELS_DIR, "best_model_violence.pth")
UCF101_MODEL_PATH   = os.path.join(MODELS_DIR, "best_ucf101.pth")

BINARY_MODELS = {
    "Fighting":  os.path.join(MODELS_DIR, "best_model_fighting.pth"),
    "Assault":   os.path.join(MODELS_DIR, "best_model_assault.pth"),
    "Vandalism": os.path.join(MODELS_DIR, "best_model_vandalism.pth"),
    "Arrest":    os.path.join(MODELS_DIR, "best_model_arrest.pth"),
    "Robbery":   os.path.join(MODELS_DIR, "best_model_robbery.pth"),
    "Burglary":  os.path.join(MODELS_DIR, "best_model_burglary.pth"),
}

IMG_SIZE = 224
CLIP_LEN = 16

# ── Thresholds ────────────────────────────────────────────────
# LIVE mode — conservative, fewer false positives
LIVE_VIOLENCE_THRESHOLD = 0.55

# VIDEO mode — more sensitive, full analysis
VIDEO_VIOLENCE_THRESHOLD = 0.50
CRIME_THRESHOLD          = 0.55
UCF_THRESHOLD            = 0.50

# Temporal smoothing
SMOOTH_WINDOW = 2  # FIX 3: was 4 — faster response to sudden violence

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

UCF101_CLASSES = [
    "ApplyEyeMakeup", "ApplyLipstick", "Archery", "BabyCrawling",
    "BalanceBeam", "BandMarching", "BaseballPitch", "Basketball",
    "BasketballDunk", "BenchPress", "Biking", "BilliardShot",
    "BlowDryHair", "BlowingCandles", "BodyWeightSquats", "Bowling",
    "BoxingPunchingBag", "BoxingSpeedBag", "Breaststroke", "BrushingTeeth",
    "CleanAndJerk", "CliffDiving", "CricketBowling", "CricketShot",
    "CuttingInKitchen", "Diving", "Drumming", "Fencing",
    "FieldHockeyPenalty", "FloorGymnastics", "FrisbeeCatch", "FrontCrawl",
    "GolfSwing", "Haircut", "HammerThrow", "Hammering",
    "HandstandPushups", "HandstandWalking", "HeadMassage", "HighJump",
    "HorseRace", "HorseRiding", "HulaHoop", "IceDancing",
    "JavelinThrow", "JugglingBalls", "JumpRope", "JumpingJack",
    "Kayaking", "Knitting", "LongJump", "Lunges",
    "MilitaryParade", "MixingBatter", "MoppingFloor", "Nunchucks",
    "ParallelBars", "PizzaTossing", "PlayingGuitar", "PlayingPiano",
    "PlayingTabla", "PlayingViolin", "PlayingCello", "PlayingDaf",
    "PlayingDhol", "PlayingFlute", "PlayingSitar", "PoleVault",
    "PommelHorse", "PullUps", "Punch", "PushUps",
    "Rafting", "RockClimbingIndoor", "RopeClimbing", "Rowing",
    "SalsaSpins", "ShavingBeard", "Shotput", "SkatBoarding",
    "Skiing", "Skijet", "SkyDiving", "SoccerJuggling",
    "SoccerPenalty", "StillRings", "SumoWrestling", "Surfing",
    "Swing", "TableTennisShot", "TaiChi", "TennisSwing",
    "ThrowDiscus", "TrampolineJumping", "Typing", "UnevenBars",
    "VolleyballSpiking", "WalkingWithDog", "WallPushups",
    "WritingOnBoard", "YoYo"
]


class SurveillanceEngine:

    def __init__(self, device=None):
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu")
        print(f"\nDevice: {self.device}")
        self.stage1_model   = None
        self.ucf101_model   = None
        self.binary_models  = {}
        self.ucf101_classes = UCF101_CLASSES
        self.violence_scores = deque(maxlen=SMOOTH_WINDOW)
        self._load_models()

    def _load(self, model, path):
        state = torch.load(path, map_location=self.device,
                           weights_only=True)
        model.load_state_dict(state, strict=False)
        return model.eval().to(self.device)

    def _load_models(self):
        print("Loading models...")
        from backend.ml.model_binary import BinaryMaxViT
        from backend.ml.model_ucf101 import UCF101VideoMAE

        self.stage1_model = self._load(
            BinaryMaxViT(num_classes=2), VIOLENCE_MODEL_PATH)
        print("  Stage 1 — Violence Detector")

        self.ucf101_model = self._load(
            UCF101VideoMAE(num_classes=101, num_frames=CLIP_LEN),
            UCF101_MODEL_PATH)
        print("  Stage 2A — UCF-101 Activity")

        for name, path in BINARY_MODELS.items():
            if os.path.exists(path):
                self.binary_models[name] = self._load(
                    BinaryMaxViT(num_classes=2), path)
                print(f"  {name} Detector")
            else:
                print(f"   {name}: not found")

        print(f"\nAll models loaded!\n")

    def preprocess(self, frames):
        processed = []
        for f in frames:
            f = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            f = cv2.resize(f, (IMG_SIZE, IMG_SIZE))
            processed.append(f)
        arr  = np.stack(processed).astype(np.float32) / 255.0
        arr  = np.transpose(arr, (0, 3, 1, 2))             # (T, C, H, W)
        clip = torch.from_numpy(np.ascontiguousarray(arr))
        clip = clip.unsqueeze(0)                            # (1, T, C, H, W)

        # FIX 1: Correct broadcast shape for (B, T, C, H, W).
        # Original was (1,3,1,1) which misaligns with the T dimension
        # and silently corrupts every frame's normalisation.
        mean = torch.tensor(IMAGENET_MEAN).view(1, 1, 3, 1, 1)
        std  = torch.tensor(IMAGENET_STD).view(1, 1, 3, 1, 1)
        clip = (clip - mean) / std

        return clip.to(self.device)

    @torch.no_grad()
    def predict(self, frames, mode="live"):
        """
        mode = "live"  → Stage 1 only (fast, reliable)
        mode = "video" → Full pipeline (detailed analysis)
        """
        if len(frames) < CLIP_LEN:
            frames = frames + [frames[-1]] * (CLIP_LEN - len(frames))
        frames = frames[:CLIP_LEN]
        clip   = self.preprocess(frames)

        # Stage 1: Violence Detection
        logits = (self.stage1_model(clip) +
                  self.stage1_model(torch.flip(clip, [4]))) / 2.0
        probs  = F.softmax(logits, dim=1)[0]
        # The model outputs [Violence, Normal]. We want the Violence probability.
        v_score = probs[0].item()

        # Temporal smoothing
        self.violence_scores.append(v_score)
        smoothed = float(np.mean(self.violence_scores))
        
        print(f"DEBUG INFERENCE: probs={probs.tolist()} v_score={v_score} smoothed={smoothed}")

        # ── LIVE MODE: Stage 1 only ───────────────────────────
        if mode == "live":
            is_violent = smoothed > LIVE_VIOLENCE_THRESHOLD
            if not is_violent:
                return {
                    "is_violent": False,
                    "activity":   "Normal",
                    "confidence": 1.0 - smoothed,
                    "v_score":    smoothed,
                    "top3":       [],
                    "all_scores": {},
                    "send_alert": False,
                }
            else:
                return {
                    "is_violent": True,
                    "activity":   "Suspicious Activity",
                    "confidence": smoothed,
                    "v_score":    smoothed,
                    "top3":       [],
                    "all_scores": {},
                    "send_alert": True,
                }

        # ── VIDEO MODE: Full pipeline ─────────────────────────
        is_violent = smoothed > VIDEO_VIOLENCE_THRESHOLD

        if not is_violent:
            # UCF-101 activity recognition
            logits101 = self.ucf101_model(clip)
            probs101  = F.softmax(logits101, dim=1)[0]
            top_idx   = probs101.argmax().item()
            top_conf  = probs101[top_idx].item()

            top3_vals, top3_idx = probs101.topk(3)
            top3 = [
                (self.ucf101_classes[i.item()], v.item())
                for i, v in zip(top3_idx, top3_vals)
            ]

            activity = (self.ucf101_classes[top_idx]
                        if top_conf >= UCF_THRESHOLD
                        else "Normal Activity")

            return {
                "is_violent": False,
                "activity":   activity,
                "confidence": top_conf,
                "v_score":    smoothed,
                "top3":       top3,
                "all_scores": {},
                "send_alert": False,
            }

        # Crime classification
        crime_scores = {}
        for name, model in self.binary_models.items():
            lgt = (model(clip) +
                   model(torch.flip(clip, [4]))) / 2.0
            p   = F.softmax(lgt, dim=1)[0]
            # The models output [CrimeType, Normal]. We want the CrimeType probability.
            crime_scores[name] = p[0].item()

        best_crime = max(crime_scores, key=crime_scores.get) \
            if crime_scores else "Violence"
        best_conf  = crime_scores.get(best_crime, smoothed)

        if best_conf < CRIME_THRESHOLD:
            best_crime = "Suspicious Activity"
            best_conf  = smoothed

        return {
            "is_violent": True,
            "activity":   best_crime,
            "confidence": best_conf,
            "v_score":    smoothed,
            "top3":       [(best_crime, best_conf)],
            "all_scores": crime_scores,
            "send_alert": True,
        }

    def reset_smoothing(self):
        self.violence_scores.clear()


def extract_frames_from_video(video_path, n_frames=CLIP_LEN):
    cap   = cv2.VideoCapture(video_path)
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total <= 0:
        cap.release()
        return []

    # FIX 2: Sample a dense consecutive window from the middle of the video
    # instead of spreading 16 frames across the entire duration.
    # Sparse sampling destroys the short-range motion patterns the model
    # was trained on (consecutive frames ≈ ~0.5 s of real action).
    # We try to grab a ~2-second dense window centred on the video midpoint.
    step  = max(1, int(fps / 8))          # ~8 samples per second → dense
    half  = (n_frames * step) // 2
    mid   = total // 2
    start = max(0, mid - half)

    idxs = [min(total - 1, start + i * step) for i in range(n_frames)]

    frames = []
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret:
            frames.append(frame)

    cap.release()

    # FIX 3: If we still got fewer than n_frames (e.g. very short clip),
    # pad by repeating the last frame — same strategy used in predict().
    while len(frames) > 0 and len(frames) < n_frames:
        frames.append(frames[-1])

    return frames