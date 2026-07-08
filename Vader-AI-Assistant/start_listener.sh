#!/bin/bash
export ANTHROPIC_API_KEY="$(security find-generic-password -a "$USER" -s ANTHROPIC_API_KEY -w 2>/dev/null)"
export ELEVENLABS_API_KEY="$(security find-generic-password -a "$USER" -s ELEVENLABS_API_KEY -w 2>/dev/null)"
export OPENWEATHERMAP_API_KEY="$(security find-generic-password -a "$USER" -s OPENWEATHERMAP_API_KEY -w 2>/dev/null)"
cd "$(dirname "$0")"
python3 -u jarvis_listen.py
