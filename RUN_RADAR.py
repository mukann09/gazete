#!/usr/bin/env python3
import RADAR_UPDATE as core
from multi_radar import fetch_multi_radar

legacy_fetch = core.fetch_radar

def combined_fetch(cfg):
    return fetch_multi_radar(cfg, legacy_fetch)

core.fetch_radar = combined_fetch

if __name__ == '__main__':
    core.main()
