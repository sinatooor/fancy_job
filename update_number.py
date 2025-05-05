#!/usr/bin/env python3
# update_number.py
# This script increments a number, commits and pushes to GitHub,
# then reschedules itself once per day to run a weighted-random number (0–5) of times today.

import os
import random
import subprocess
from datetime import datetime

# Determine the directory where this script resides
script_dir = os.path.dirname(os.path.abspath(__file__))
# Change working directory to the script directory
os.chdir(script_dir)


def read_number():
    """
    Read the current integer value from number.txt.
    """
    with open("number.txt", "r") as f:
        return int(f.read().strip())


def write_number(num):
    """
    Write the integer `num` to number.txt.
    """
    with open("number.txt", "w") as f:
        f.write(str(num))


def generate_random_commit_message():
    """
    Use an LLM to generate a Conventional Commits–style message.
    """
    from transformers import pipeline

    generator = pipeline(
        "text-generation",
        model="openai-community/gpt2",
    )
    prompt = """
        Generate a Git commit message following the Conventional Commits standard.
        The message should include a type, an optional scope, and a subject. Please keep it short.
        """
    generated = generator(
        prompt,
        max_new_tokens=50,
        num_return_sequences=1,
        temperature=0.9,
        top_k=50,
        top_p=0.9,
        truncation=True,
    )
    text = generated[0]["generated_text"]

    # Extract the text after the last bullet
    if "- " in text:
        return text.rsplit("- ", 1)[-1].strip()
    else:
        raise ValueError(f"Unexpected generated text {text}")


def git_commit():
    """
    Stage number.txt and commit with either a random LLM-generated message or today’s date.
    """
    subprocess.run(["git", "add", "number.txt"])
    if "FANCY_JOB_USE_LLM" in os.environ:
        commit_message = generate_random_commit_message()
    else:
        date = datetime.now().strftime("%Y-%m-%d")
        commit_message = f"Update number: {date}"
    subprocess.run(["git", "commit", "-m", commit_message])


def git_push():
    """
    Push committed changes to GitHub, and report success or error.
    """
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print("Changes pushed to GitHub successfully.")
    else:
        print("Error pushing to GitHub:")
        print(result.stderr)


def update_cron_random_times():
    """
    Once per day, reschedule this script to run a weighted-random number of times (0–5) today.
    This guard ensures existing schedules for the day aren't overwritten by subsequent runs.
    """
    cron_file = "/tmp/current_cron"
    today_str = datetime.now().strftime("%Y-%m-%d")
    schedule_marker = os.path.join(script_dir, "cron_schedule_date.txt")

    # If we've already scheduled today, skip rescheduling
    if os.path.exists(schedule_marker):
        with open(schedule_marker, "r") as f:
            if f.read().strip() == today_str:
                print("Cron already scheduled for today. Skipping.")
                return

    # Dump existing crontab to temp file (or create empty)
    os.system(f"crontab -l > {cron_file} 2>/dev/null || true")

    # Read and filter out old entries for this script
    with open(cron_file, "r") as f:
        existing = [ln for ln in f if "update_number.py" not in ln]

    # Define percentage weights for run counts 0 through 9 (higher counts less likely)
    PROB_WEIGHTS = [15, 25, 15, 10, 9, 8, 7, 5, 3, 3]
    # Select run_count based on weighted probabilities
    run_count = random.choices(range(len(PROB_WEIGHTS)), weights=PROB_WEIGHTS, k=1)[0]

    # Generate unique (hour, minute) pairs for run_count
    n=0
    times = set()
    while len(times) < run_count:
        h = random.randint(0, 23)
        m = random.randint(0, 59)
        times.add((h, m))
        n+=1

    # Build new cron lines with logging
    log_file = os.path.join(script_dir, "cron_update.log")
    new_lines = []
    for h, m in sorted(times):
        new_lines.append(
            f"{m} {h} * * * cd {script_dir} && "
            f"/usr/bin/env python3 {os.path.join(script_dir, 'update_number.py')} "
            f">> {log_file} 2>&1\n"
        )

    # Write back the filtered lines plus new entries
    with open(cron_file, "w") as f:
        f.writelines(existing)
        f.writelines(new_lines)

    # Install the updated crontab
    os.system(f"crontab {cron_file}")
    os.remove(cron_file)

    # Mark scheduling done for today
    with open(schedule_marker, "w") as f:
        f.write(today_str)

    print(f"Scheduled {run_count} run(s) today at: {sorted(times)}")
    # Get current local date & time
    now = datetime.now()

    # Print full datetime
    print(now.strftime("%Y-%m-%d %H:%M:%S")) 


def main():
    """
    Main workflow:
    1. Read and increment the number
    2. Commit & push to GitHub
    3. Reschedule cron jobs once per day
    """
    try:
        current_number = read_number()
        new_number = current_number + 1
        write_number(new_number)
        git_commit()
        git_push()
        update_cron_random_times()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
