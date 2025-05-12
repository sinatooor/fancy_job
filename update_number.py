#!/usr/bin/env python3
# update_number.py
# This script increments a number, commits and pushes to GitHub,
# then reschedules itself daily to run a weighted-random number of times.
# Four fixed scheduler entries at 00:01, 10:00, 15:00, and 20:00 ensure
# it always schedules new runs even on zero-run days.

import os
import random
import subprocess
import argparse
from datetime import datetime

# --- Paths and markers ---
# Directory where this script resides
script_dir      = os.path.dirname(os.path.abspath(__file__))
# Full path to this script file
script_path     = os.path.join(script_dir, "update_number.py")
# Temporary file for storing current crontab
cron_file       = "/tmp/current_cron"
# Marker file to track if scheduling has been done today
schedule_marker = os.path.join(script_dir, "cron_schedule_date.txt")
# Log file for cron execution output
log_file        = os.path.join(script_dir, "cron_update.log")


def read_number():
    """
    Read the current integer from number.txt (must exist).
    """
    with open("number.txt", "r") as f:
        return int(f.read().strip())


def write_number(num):
    """
    Write the integer `num` back to number.txt, overwriting the old value.
    """
    with open("number.txt", "w") as f:
        f.write(str(num))


def generate_random_commit_message():
    """
    (Optional) Use an LLM to generate a Conventional Commits style message.
    Falls back to date-based message if LLM is disabled.
    """
    from transformers import pipeline
    generator = pipeline("text-generation", model="openai-community/gpt2")
    prompt = (
        "Generate a Git commit message following the Conventional Commits standard.\n"
        "Keep it short."
    )
    result = generator(
        prompt,
        max_new_tokens=50,
        num_return_sequences=1,
        temperature=0.9,
        top_k=50,
        top_p=0.9,
        truncation=True,
    )
    text = result[0]["generated_text"]
    # Extract text after last bullet, if present
    if "- " in text:
        return text.rsplit("- ", 1)[-1].strip()
    raise ValueError(f"Unexpected generated text {text}")


def git_commit():
    """
    Stage and commit number.txt with either an LLM message or today's date.
    """
    subprocess.run(["git", "add", "number.txt"])
    if "FANCY_JOB_USE_LLM" in os.environ:
        msg = generate_random_commit_message()
    else:
        msg = f"Update number: {datetime.now():%Y-%m-%d}"
    subprocess.run(["git", "commit", "-m", msg])


def git_push():
    """
    Push committed changes to GitHub and print success or error output.
    """
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print("Pushed successfully.")
        now = datetime.now()
        # Print full datetime
        print(now.strftime("%Y-%m-%d %H:%M:%S")) 
        
    else:
        print("Push error:", result.stderr)


def update_cron_random_times():
    """
    Cleanup old RANDOM entries and schedule 0–9 new RANDOM runs for today.
    Fixed scheduler entries (# [FIXED]) remain untouched.
    Uses a marker file to ensure it only runs once per day.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Only schedule once per day
    if os.path.exists(schedule_marker) and open(schedule_marker).read().strip() == today_str:
        print("Already scheduled today; skipping.")
        return

    # Dump existing crontab to a temp file (ignore errors)
    os.system(f"crontab -l > {cron_file} 2>/dev/null || true")
    with open(cron_file, "r") as f:
        lines = f.readlines()

    # Retain all FIXED entries and any other crontab lines
    existing = []
    for ln in lines:
        if "# [RANDOM]" in ln:
            # drop old random-run entries
            continue
        existing.append(ln)

    # Weighted probabilities for selecting 0–9 runs
    PROB_WEIGHTS = [13, 15, 17, 4, 11, 9, 8, 6, 5, 12]
    #run_count = 8
    run_count = random.choices(range(len(PROB_WEIGHTS)), weights=PROB_WEIGHTS, k=1)[0]
    
    
    # Generate unique (hour,minute) tuples
    times = set()
    hours = list(range(0, 2)) + list(range(6, 24))
    while len(times) < run_count:
        h = random.choice(hours)
        m = random.randint(0, 59)
        times.add((h, m))

    # Append new RANDOM cron entries
    for h, m in sorted(times):
        existing.append(
            f"{m} {h} * * * cd {script_dir} && "
            f"/usr/bin/env python3 {script_path} >> {log_file} 2>&1  # [RANDOM]\n"
        )

    # Write and install updated crontab
    with open(cron_file, "w") as f:
        f.writelines(existing)
    os.system(f"crontab {cron_file}")
    os.remove(cron_file)

    # Update marker file
    with open(schedule_marker, "w") as f:
        f.write(today_str)

    print(f"Scheduled {run_count} RANDOM run(s) today at: {sorted(times)}")
    
    now = datetime.now()
    # Print full datetime
    print(now.strftime("%Y-%m-%d %H:%M:%S")) 

def do_update():
    """
    Perform the actual update: increment the number, commit and push.
    """
    current = read_number()
    write_number(current + 1)
    git_commit()
    git_push()


def main():
    """
    Parse `--schedule` flag. Without it, run update; with it, only reschedule.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="only reschedule RANDOM runs; do not bump number or push"
    )
    args = parser.parse_args()

    if args.schedule:
        update_cron_random_times()
    else:
        do_update()


if __name__ == "__main__":
    main()
