import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import re
import json
import shutil
from pathlib import Path

novel_root = Path(r"d:\Novel")
projects_dir = novel_root / "projects"

def parse_characters(chars_file):
    if not chars_file.exists(): return []
    content = chars_file.read_text(encoding="utf-8")
    nodes = []
    sections = re.split(r'\n(?=##\s+\[CHAR-\d+\])', content)
    
    faction_colors = {
        "Nhân vật chính": "#8b5cf6",
        "Học Viện Tháp": "#38bdf8",
        "Dũng Giả & Giáo Hội": "#fbbf24",
        "Vương Quốc Goma": "#ef4444",
        "Vương Quốc Astoria": "#10b981",
        "Gia Tộc Rosenberg": "#ec4899",
        "Hoàng Gia": "#f59e0b",
        "Khác": "#94a3b8"
    }

    for sec in sections:
        m = re.search(r'##\s+\[(CHAR-\d+)\]\s+([^\n]+)', sec)
        if not m: continue
        eid, name = m.group(1).strip(), m.group(2).strip()
        
        faction_m = re.search(r'(?:Phe phái|Tổ chức|Phe):\s*([^\n]+)', sec, re.IGNORECASE)
        faction = faction_m.group(1).strip() if faction_m else "Khác"
        
        role_m = re.search(r'(?:Vai trò|Chức nghiệp|Nghề nghiệp):\s*([^\n]+)', sec, re.IGNORECASE)
        role = role_m.group(1).strip() if role_m else "Nhân vật"
        
        desc_m = re.search(r'(?:Mô tả|Đặc điểm):\s*([^\n]+)', sec, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        color = faction_colors.get(faction, "#38bdf8")
        if "Momokawa" in name or "Aurelia" in name or "Chính" in faction:
            color = "#8b5cf6"
            faction = "Nhân vật chính"

        nodes.append({
            "id": name,
            "label": name,
            "name_orig": name,
            "eid": eid,
            "faction": faction,
            "color": color,
            "role": role,
            "description": desc,
            "skills": [],
            "timeline": []
        })
    return nodes

def parse_relationships(rel_file):
    if not rel_file.exists(): return []
    content = rel_file.read_text(encoding="utf-8")
    edges = []
    
    lines = content.splitlines()
    for l in lines:
        m = re.search(r'(?:\*\*|\[)?([A-Za-zÀ-ỹ\s_0-9]+)(?:\*\*|\])?\s*(?:<->|->|→|—|quan hệ với)\s*(?:\*\*|\[)?([A-Za-zÀ-ỹ\s_0-9]+)(?:\*\*|\])?:\s*(.+)', l)
        if m:
            u, v, label = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if u and v and len(u) > 1 and len(v) > 1:
                color = "#94a3b8"
                if any(w in label.lower() for w in ["yêu", "hôn thê", "bạn đời", "tình cảm"]): color = "#ec4899"
                elif any(w in label.lower() for w in ["kẻ thù", "đối đầu", "căm ghét", "phản bội"]): color = "#ef4444"
                elif any(w in label.lower() for w in ["đồng minh", "bạn bè", "tin tưởng", "hầu cận"]): color = "#10b981"
                
                edges.append({
                    "from": u,
                    "to": v,
                    "label": label[:30],
                    "color": color,
                    "nature": label
                })
    return edges

def parse_locations(loc_file, novel_key):
    if not loc_file.exists():
        if "Chu_Thuat_Su" in novel_key:
            return [
                {"id": "Thị Trấn Di Tích", "name": "Thị Trấn Di Tích", "type": "TOWN", "icon": "🏛️", "color": "#38bdf8", "x": 300, "y": 250, "desc": "Nơi các học sinh hạ trại và khám phá tàn tích."},
                {"id": "Học Viện Tháp", "name": "Học Viện Tháp", "type": "TOWER", "icon": "🗼", "color": "#fbbf24", "x": 600, "y": 200, "desc": "Căn cứ của nhóm học viện do Tendou chỉ huy."},
                {"id": "Hang Động Khởi Đầu", "name": "Hang Động Khởi Đầu", "type": "DUNGEON", "icon": "⛰️", "color": "#a855f7", "x": 150, "y": 400, "desc": "Nơi Kotarou thức tỉnh thiên chức Chú Thuật Sư."},
                {"id": "Vương Quốc Goma", "name": "Vương Quốc Goma", "type": "KINGDOM", "icon": "🏰", "color": "#ef4444", "x": 750, "y": 450, "desc": "Vương quốc của chủng tộc Goma."}
            ]
        elif "Ác Nữ" in novel_key:
            return [
                {"id": "Học Viện Hoàng Gia", "name": "Học Viện Hoàng Gia & Phòng Hội Học Sinh", "type": "ACADEMY", "icon": "🏫", "color": "#38bdf8", "x": 200, "y": 200, "desc": "Nơi diễn ra vụ ngã cầu thang định mệnh."},
                {"id": "Biệt Thự Suối Nước Nóng", "name": "Biệt Thự Suối Nước Nóng Rosenberg", "type": "MANSION", "icon": "♨️", "color": "#ec4899", "x": 480, "y": 180, "desc": "Nơi Aurelia lui về dưỡng thương sau khi hủy hôn ước."},
                {"id": "Khu Phố Ẩm Thực", "name": "Khu Phố Ẩm Thực Lãnh Địa Rosenberg", "type": "TOWN", "icon": "🍷", "color": "#10b981", "x": 420, "y": 380, "desc": "Nơi Aurelia thưởng thức ẩm thực và bánh kẹo."},
                {"id": "Lâu Đài Vương Đô", "name": "Lâu Đài Vương Đô Grandier", "type": "CASTLE", "icon": "👑", "color": "#f59e0b", "x": 700, "y": 220, "desc": "Nơi ở của Hoàng tộc và Tam Công Chúa Beatrice."}
            ]
        else:
            return [
                {"id": "Thị Trấn Khởi Đầu", "name": "Thị Trấn Khởi Đầu", "type": "TOWN", "icon": "🏡", "color": "#38bdf8", "x": 300, "y": 300, "desc": "Khu vực sinh sống của nhân vật chính."}
            ]

    content = loc_file.read_text(encoding="utf-8")
    locs = []
    sections = re.split(r'\n(?=##\s+)', content)
    default_coords = [(200, 200), (450, 200), (300, 400), (650, 350), (150, 450), (500, 500)]
    idx = 0

    for sec in sections:
        m = re.search(r'##\s+(?:\[LOC-\d+\]\s+)?([^\n]+)', sec)
        if not m: continue
        name = m.group(1).strip()
        desc_m = re.search(r'(?:Mô tả|Đặc điểm|Chi tiết):\s*([^\n]+)', sec, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""
        
        cx, cy = default_coords[idx % len(default_coords)]
        idx += 1

        locs.append({
            "id": name,
            "name": name,
            "type": "LOCATION",
            "icon": "📍",
            "color": "#38bdf8",
            "x": cx,
            "y": cy,
            "desc": desc
        })
    return locs

def build_all():
    novel_dirs = [d for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    all_graphs = {}
    all_maps = {}

    for d in novel_dirs:
        key = d.name
        title = key.replace("_", " ")
        glossary_dir = d / "glossary"
        
        nodes = parse_characters(glossary_dir / "characters.md")
        edges = parse_relationships(glossary_dir / "relationship_timeline.md")
        factions = list(set([n["faction"] for n in nodes])) if nodes else ["Nhân vật chính", "Khác"]
        
        all_graphs[key] = {
            "novel_key": key,
            "novel_title": title,
            "nodes": nodes,
            "edges": edges,
            "factions": factions
        }

        locs = parse_locations(glossary_dir / "locations.md", key)
        all_maps[key] = {
            "novel_key": key,
            "novel_title": title,
            "locations": locs
        }

    graph_js = f"window.GRAPH_DATA = {json.dumps(all_graphs, ensure_ascii=False, indent=2)};\n"
    map_js = f"window.MAP_DATA = {json.dumps(all_maps, ensure_ascii=False, indent=2)};\n"

    for root in [novel_root, Path(r"d:\Novel_Sandbox")]:
        (root / "web" / "graph_data.js").write_text(graph_js, encoding="utf-8")
        (root / "graph_data.js").write_text(graph_js, encoding="utf-8")
        
        (root / "web" / "map_data.js").write_text(map_js, encoding="utf-8")
        (root / "map_data.js").write_text(map_js, encoding="utf-8")
        
        for h in ["Ban_Do_The_Gioi.html", "So_Do_Quan_He.html", "So_Sanh_Diff.html", "Bao_Cao_Chuan_Hoa.html", "Kiem_Tra_Cache_Token.html"]:
            src = root / "web" / h
            if src.exists():
                (root / h).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Lưu tool build_map_and_graph.py vào tools/
    script_content = Path(__file__).read_text(encoding="utf-8")
    (novel_root / "tools" / "build_map_and_graph.py").write_text(script_content, encoding="utf-8")
    (Path(r"d:\Novel_Sandbox") / "tools" / "build_map_and_graph.py").write_text(script_content, encoding="utf-8")

    print(f"🎉 Đã tự động cập nhật map_data.js và graph_data.js cho {len(novel_dirs)} bộ truyện!")

if __name__ == "__main__":
    build_all()
