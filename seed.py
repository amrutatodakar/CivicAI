"""Idempotent synthetic demo dataset for CivicAI.

All names, addresses and coordinates are fictional and exist only to exercise
the application. Running this twice does not duplicate records.
"""
import json
import random
from datetime import timedelta

from flask import current_app

from extensions import db
from models import (
    ActivityLog,
    AppSetting,
    Complaint,
    DuplicateLink,
    STATUSES,
    StatusHistory,
    utcnow,
)
from services.ai_service import analyze_complaint
from services.complaint_service import update_suggested_links
from services.duplicate_service import find_duplicates
from services.priority_service import score_priority

SEED_VERSION = "1"

# title, description, address, lat, lng, status, days_ago
DEMO_COMPLAINTS = [
    (
        "Deep pothole beside college bus stop",
        "A huge pothole is present near the college bus stop. Several vehicles are swerving to avoid it and someone may get injured.",
        "College Road, Demo City",
        22.3116,
        73.1817,
        "Submitted",
        0.1,
    ),
    (
        "Large hole near college bus stand",
        "The road has a large hole near the college bus stand. Two-wheelers are swerving into traffic and students risk an accident.",
        "College Road, Demo City",
        22.3117,
        73.1818,
        "Submitted",
        0.5,
    ),
    (
        "Pothole at College Road crossing",
        "There is a deep pothole at the College Road crossing. Cars slow down suddenly and it is dangerous at night.",
        "College Road, Demo City",
        22.3112,
        73.1814,
        "Under Review",
        1.0,
    ),
    (
        "Knee-deep water at college gate",
        "Waterlogging near the college main gate is knee-deep after rain. Students are wading through the water and the road is flooded.",
        "College Road, Demo City",
        22.3119,
        73.1810,
        "Submitted",
        0.8,
    ),
    (
        "Road flooded near college entrance",
        "The road near the college entrance is flooded with standing water. Water has entered the nearby shops and buses cannot stop safely.",
        "College Road, Demo City",
        22.3120,
        73.1812,
        "Under Review",
        1.2,
    ),
    (
        "Blocked drain behind college canteen",
        "The drainage drain behind the college canteen is blocked and overflowing. Stagnant water is creating a bad smell and mosquitoes.",
        "College Road, Demo City",
        22.3110,
        73.1820,
        "Assigned",
        2.0,
    ),
    (
        "Overflowing drain on College Road",
        "An open drain on College Road is overflowing onto the pavement. Residents complain of stagnant water and the risk of slipping.",
        "College Road, Demo City",
        22.3113,
        73.1816,
        "Resolved",
        12.0,
    ),
    (
        "Garbage bin overflowing near college canteen",
        "The garbage bin near the college canteen is overflowing. Trash is scattered on the road and there is a strong smell.",
        "College Road, Demo City",
        22.3118,
        73.1822,
        "Submitted",
        1.5,
    ),
    (
        "Streetlight not working near college library",
        "The streetlight near the college library has not working for three days. The street is dark and students feel unsafe walking at night.",
        "College Road, Demo City",
        22.3108,
        73.1812,
        "In Progress",
        4.0,
    ),
    (
        "Road cave-in near college bus stop",
        "The road has collapsed near the college bus stop and a deep hole has formed. A bus tyre got stuck and passengers may be injured.",
        "College Road, Demo City",
        22.3114,
        73.1819,
        "Submitted",
        0.3,
    ),
    (
        "Garbage pile at Gandhi Market",
        "A large garbage pile has formed at Gandhi Market. Waste is rotting in the open and shoppers are complaining about the smell.",
        "Gandhi Market, Demo City",
        22.3056,
        73.1742,
        "Under Review",
        2.0,
    ),
    (
        "Trash dumped behind Gandhi Market shops",
        "Garbage and trash have been dumped behind the Gandhi Market shops. The pile is attracting stray dogs and blocking the footpath.",
        "Gandhi Market, Demo City",
        22.3058,
        73.1743,
        "Submitted",
        2.5,
    ),
    (
        "Drain blocked at Gandhi Market",
        "The sewer drain at Gandhi Market is blocked and black water is overflowing near the vegetable stalls. It is a health hazard.",
        "Gandhi Market, Demo City",
        22.3054,
        73.1738,
        "Assigned",
        3.0,
    ),
    (
        "Market flooded after rain",
        "Gandhi Market is flooded after rain. Standing water is ankle-deep and customers are unable to reach the shops.",
        "Gandhi Market, Demo City",
        22.3052,
        73.1740,
        "In Progress",
        1.8,
    ),
    (
        "Cracked road outside market",
        "The road outside Gandhi Market has large cracks and broken asphalt. Carts are getting stuck and the surface is uneven.",
        "Gandhi Market, Demo City",
        22.3059,
        73.1746,
        "Resolved",
        14.0,
    ),
    (
        "Dark streetlight near market gate",
        "The streetlight near the Gandhi Market gate is not working. The area is dark and unsafe for women and elderly shoppers in the evening.",
        "Gandhi Market, Demo City",
        22.3053,
        73.1747,
        "Assigned",
        5.0,
    ),
    (
        "Waterlogging in Lakeview Colony",
        "Lakeview Colony has severe waterlogging after every rain. The water stands for two days and is entering ground-floor homes.",
        "Lakeview Colony, Demo City",
        22.3188,
        73.1906,
        "Submitted",
        1.1,
    ),
    (
        "Flooded lane in Lakeview",
        "The lane in Lakeview Colony is flooded with knee-deep water. Children cannot go to school and residents are trapped.",
        "Lakeview Colony, Demo City",
        22.3189,
        73.1909,
        "Under Review",
        2.0,
    ),
    (
        "Drain overflow in Lakeview",
        "The drainage line in Lakeview Colony is overflowing. Sewage is flowing on the road and there is a strong smell.",
        "Lakeview Colony, Demo City",
        22.3186,
        73.1907,
        "Assigned",
        3.0,
    ),
    (
        "Garbage collection missed in Lakeview",
        "Garbage has not been collected in Lakeview Colony for five days. Bins are overflowing and waste is piling up near the park.",
        "Lakeview Colony, Demo City",
        22.3190,
        73.1910,
        "Submitted",
        2.2,
    ),
    (
        "Pothole on Lakeview main road",
        "A large pothole on the Lakeview main road is causing vehicles to swerve. It becomes invisible when the road is flooded.",
        "Lakeview Colony, Demo City",
        22.3184,
        73.1905,
        "In Progress",
        4.0,
    ),
    (
        "Streetlight not working in Sector 12",
        "The streetlight near the Sector 12 community centre is not working. The whole lane is dark at night and unsafe.",
        "Sector 12, Demo City",
        22.2996,
        73.1886,
        "Submitted",
        1.0,
    ),
    (
        "Dark lane in Sector 12",
        "Several streetlights are not working in the Sector 12 lane. The entire street is dark and residents are afraid to walk after 8 pm.",
        "Sector 12, Demo City",
        22.2997,
        73.1884,
        "Under Review",
        1.5,
    ),
    (
        "Damaged road in Sector 12",
        "The road in Sector 12 is badly damaged with deep cracks and loose gravel. Cyclists are skidding and falling.",
        "Sector 12, Demo City",
        22.2994,
        73.1888,
        "Assigned",
        6.0,
    ),
    (
        "Garbage dump near Sector 12 park",
        "A garbage dump has appeared near the Sector 12 park. Waste is scattered around and children play next to it.",
        "Sector 12, Demo City",
        22.2992,
        73.1882,
        "Submitted",
        2.8,
    ),
    (
        "Open manhole in Sector 12",
        "An open manhole in Sector 12 is a serious hazard. Children walk past it and someone could fall in at night.",
        "Sector 12, Demo City",
        22.2998,
        73.1889,
        "Submitted",
        0.6,
    ),
    (
        "Blocked drain in Sector 12",
        "The drain in Sector 12 is blocked and water is overflowing onto the road. There is stagnant water and mosquito breeding.",
        "Sector 12, Demo City",
        22.2993,
        73.1885,
        "In Progress",
        7.0,
    ),
    (
        "Garbage pile at Old Bus Stand",
        "Garbage is piling up at the Old Bus Stand. The bins are overflowing and passengers are forced to stand near the waste.",
        "Old Bus Stand, Demo City",
        22.3141,
        73.1706,
        "Submitted",
        1.4,
    ),
    (
        "Stray dogs near Old Bus Stand",
        "A pack of stray dogs is roaming near the Old Bus Stand and chasing passengers. Children may be injured.",
        "Old Bus Stand, Demo City",
        22.3139,
        73.1704,
        "Under Review",
        3.0,
    ),
    (
        "Waterlogged bus stand road",
        "The road at the Old Bus Stand is waterlogged after rain. Buses are splashing water on passengers and the shelter is flooded.",
        "Old Bus Stand, Demo City",
        22.3142,
        73.1707,
        "Assigned",
        2.1,
    ),
    (
        "Broken road at Old Bus Stand",
        "The road at the Old Bus Stand is broken and uneven. Passengers are tripping near the loading bay.",
        "Old Bus Stand, Demo City",
        22.3137,
        73.1703,
        "Resolved",
        16.0,
    ),
    (
        "Streetlight out at Old Bus Stand",
        "The streetlight at the Old Bus Stand is not working. Passengers wait in the dark and the area feels unsafe.",
        "Old Bus Stand, Demo City",
        22.3140,
        73.1709,
        "Assigned",
        4.0,
    ),
    (
        "Garbage bins overflow in Sunrise Colony",
        "Garbage bins in Sunrise Colony are overflowing and waste is lying on the street. The smell is unbearable.",
        "Sunrise Colony, Demo City",
        22.2956,
        73.1826,
        "Submitted",
        0.9,
    ),
    (
        "Waterlogging in Sunrise Colony",
        "Sunrise Colony is waterlogged after heavy rain. Standing water has entered the lane and residents cannot reach the main road.",
        "Sunrise Colony, Demo City",
        22.2954,
        73.1824,
        "Under Review",
        2.0,
    ),
    (
        "Sewer blocked in Sunrise Colony",
        "The sewer line in Sunrise Colony is blocked. Sewage is backing up into the street and there is a health hazard.",
        "Sunrise Colony, Demo City",
        22.2958,
        73.1828,
        "In Progress",
        5.0,
    ),
    (
        "Pothole near Sunrise Colony gate",
        "A deep pothole near the Sunrise Colony gate is damaging vehicles. It fills with water and is hidden from view.",
        "Sunrise Colony, Demo City",
        22.2952,
        73.1822,
        "Assigned",
        3.5,
    ),
    (
        "Broken wall near Sunrise park",
        "A public wall near the Sunrise Colony park has collapsed. Bricks are on the footpath and children could get hurt.",
        "Sunrise Colony, Demo City",
        22.2959,
        73.1830,
        "Submitted",
        1.7,
    ),
    (
        "Damaged riverside walkway",
        "The riverside walkway has broken pavement and loose stones. Pedestrians and joggers are tripping.",
        "Riverside Park, Demo City",
        22.3216,
        73.1666,
        "Resolved",
        18.0,
    ),
    (
        "Streetlight off at Riverside Park",
        "The streetlight at the Riverside Park entrance is not working. The park gate is dark in the evening and unsafe.",
        "Riverside Park, Demo City",
        22.3214,
        73.1664,
        "Under Review",
        2.5,
    ),
    (
        "Garbage at Riverside Park",
        "Garbage is scattered around Riverside Park after the weekend. Plastic waste is blowing into the river.",
        "Riverside Park, Demo City",
        22.3217,
        73.1668,
        "Submitted",
        1.3,
    ),
    (
        "Waterlogging at Riverside Park gate",
        "Waterlogging at the Riverside Park gate is making the path slippery. Standing water has been there for three days.",
        "Riverside Park, Demo City",
        22.3213,
        73.1662,
        "Assigned",
        4.0,
    ),
    (
        "Unsafe broken bench in park",
        "A broken public bench in Riverside Park has exposed sharp metal edges. Children play nearby and could be injured.",
        "Riverside Park, Demo City",
        22.3215,
        73.1670,
        "Resolved",
        20.0,
    ),
    (
        "Pothole on Metro Station Road",
        "A large pothole on Metro Station Road is causing traffic to slow down. Commuters on two-wheelers are at risk of an accident.",
        "Metro Station Road, Demo City",
        22.3205,
        73.1745,
        "Submitted",
        0.4,
    ),
    (
        "Damaged road near City Hospital",
        "The road near City Hospital is damaged and ambulances are struggling to pass. The uneven surface is delaying emergency vehicles.",
        "City Hospital Road, Demo City",
        22.3080,
        73.1920,
        "Submitted",
        0.7,
    ),
    (
        "Streetlight not working near school",
        "The streetlight outside the primary school is not working. Children walk home in the dark and parents are worried about safety.",
        "School Lane, Demo City",
        22.3020,
        73.1690,
        "In Progress",
        2.6,
    ),
    (
        "Garbage near Green Park",
        "Garbage is dumped near Green Park and the bins are overflowing. Residents say collection has been irregular for a week.",
        "Green Park, Demo City",
        22.3170,
        73.1780,
        "Assigned",
        4.5,
    ),
    (
        "Blocked drain on Ward 7 road",
        "The drain on the Ward 7 road is blocked with silt and plastic. Rainwater is overflowing onto the street.",
        "Ward 7, Demo City",
        22.3030,
        73.1800,
        "Under Review",
        3.2,
    ),
    (
        "Waterlogging on Market Road",
        "Market Road is waterlogged and the drain is overflowing. Shoppers are wading through dirty water.",
        "Market Road, Demo City",
        22.3045,
        73.1765,
        "In Progress",
        1.6,
    ),
    (
        "Live wire hanging near Park Street",
        "A live electrical wire is hanging low near Park Street. Pedestrians could be electrocuted and children are playing nearby.",
        "Park Street, Demo City",
        22.3075,
        73.1850,
        "Submitted",
        0.2,
    ),
    (
        "Broken footpath on Station Road",
        "The footpath on Station Road is broken and uneven. Pedestrians are stepping onto the road and risking an accident.",
        "Station Road, Demo City",
        22.3160,
        73.1690,
        "Assigned",
        5.5,
    ),
    (
        "Overflowing garbage at Community Centre",
        "The garbage bin at the Community Centre is overflowing. Waste is spread on the ground and smells bad.",
        "Community Centre, Demo City",
        22.3090,
        73.1710,
        "Resolved",
        11.0,
    ),
    (
        "Streetlight repaired in Lakeview",
        "The streetlight near Lakeview park was not working for a week. It is now repaired but residents want regular checks.",
        "Lakeview Colony, Demo City",
        22.3192,
        73.1912,
        "Resolved",
        9.0,
    ),
    (
        "Pothole fixed on College Road",
        "A pothole near the College Road bus stop was repaired last month but the surface is breaking again.",
        "College Road, Demo City",
        22.3105,
        73.1808,
        "Resolved",
        22.0,
    ),
    (
        "Garbage cleared in Sector 12",
        "Garbage near the Sector 12 market was cleared after complaints. The bins still need a regular collection schedule.",
        "Sector 12, Demo City",
        22.3002,
        73.1892,
        "Resolved",
        13.0,
    ),
]

STATUS_NOTES = {
    "Under Review": "Complaint reviewed by the civic operations desk.",
    "Assigned": "Assigned to the responsible department for inspection.",
    "In Progress": "Field team has started work at the reported location.",
    "Resolved": "Work completed and marked resolved after field verification.",
}


def _seed_history(complaint, created_at, target_status, department):
    target_index = STATUSES.index(target_status)
    db.session.add(
        StatusHistory(
            complaint_id=complaint.id,
            previous_status=None,
            new_status="Submitted",
            note="Complaint received and automatically analysed.",
            is_public=True,
            created_at=created_at,
        )
    )
    db.session.add(
        ActivityLog(
            complaint_id=complaint.id,
            event_type="submitted",
            message="Synthetic demo complaint loaded by seed script.",
            actor="seed_script",
            created_at=created_at,
        )
    )
    event_time = created_at
    now = utcnow()
    for index in range(1, target_index + 1):
        status = STATUSES[index]
        candidate_time = created_at + timedelta(hours=5 * index)
        candidate_time = min(candidate_time, now - timedelta(minutes=20))
        if candidate_time <= event_time:
            candidate_time = event_time + timedelta(minutes=5)
        event_time = candidate_time
        db.session.add(
            StatusHistory(
                complaint_id=complaint.id,
                previous_status=STATUSES[index - 1],
                new_status=status,
                note=STATUS_NOTES.get(status),
                is_public=True,
                created_at=event_time,
            )
        )
        db.session.add(
            ActivityLog(
                complaint_id=complaint.id,
                event_type="workflow_update",
                message=f"Status changed from {STATUSES[index - 1]} to {status}.",
                actor="demo_officer",
                created_at=event_time,
            )
        )
    complaint.updated_at = event_time


def _clear_all():
    DuplicateLink.query.delete()
    ActivityLog.query.delete()
    StatusHistory.query.delete()
    Complaint.query.delete()
    AppSetting.query.filter(AppSetting.key.in_(["complaint_counter", "seed_version"])).delete(
        synchronize_session=False
    )
    db.session.commit()


def seed_database(force=False):
    marker = db.session.get(AppSetting, "seed_version")
    if marker and not force:
        return {"seeded": False, "reason": "Synthetic demo data is already loaded."}
    if Complaint.query.count() and not force:
        AppSetting.query.filter_by(key="seed_version").delete()
        db.session.add(AppSetting(key="seed_version", value=SEED_VERSION))
        db.session.commit()
        return {
            "seeded": False,
            "reason": "Complaints already exist; existing records were preserved.",
        }

    if force:
        _clear_all()

    random.seed(42)
    now = utcnow()
    created_complaints = []
    for index, row in enumerate(DEMO_COMPLAINTS, start=1):
        title, description, address, lat, lng, status, days_ago = row
        created_at = now - timedelta(days=days_ago, hours=random.randint(0, 5))
        analysis = analyze_complaint(
            title=title,
            description=description,
            selected_category=None,
            duplicate_count=0,
            has_image=False,
            has_location=True,
        )
        rank = STATUSES.index(status)
        department = analysis["recommended_department"] if rank >= 2 else None
        complaint = Complaint(
            public_id=f"CIV-{index:04d}",
            title=title,
            description=description,
            ai_summary=analysis["summary"],
            category=analysis["category"],
            category_confidence=analysis["category_confidence"],
            priority_score=analysis["priority_score"],
            priority_level=analysis["priority_level"],
            priority_explanation=analysis["priority_explanation"],
            priority_factors=json.dumps(analysis["priority_factors"]),
            recommended_department=analysis["recommended_department"],
            ai_engine=analysis["ai_engine"],
            ai_notes=analysis["ai_notes"] + " Synthetic demo record.",
            latitude=lat,
            longitude=lng,
            address=address,
            status=status,
            assigned_department=department,
            created_at=created_at,
            updated_at=created_at,
        )
        db.session.add(complaint)
        db.session.flush()
        _seed_history(complaint, created_at, status, department)
        created_complaints.append(complaint)

    db.session.add(AppSetting(key="complaint_counter", value=str(len(created_complaints))))
    db.session.commit()

    # Detect duplicates only against earlier records to avoid symmetric pairs.
    duplicate_counts = {complaint.id: 0 for complaint in created_complaints}
    for i, complaint in enumerate(created_complaints):
        earlier = created_complaints[:i]
        if not earlier:
            continue
        results = find_duplicates(complaint, earlier, current_app.config)
        if results:
            update_suggested_links(complaint, results)
            for result in results:
                duplicate_counts[complaint.id] += 1
                duplicate_counts[result["complaint"].id] += 1
    db.session.commit()

    for complaint in created_complaints:
        count = duplicate_counts.get(complaint.id, 0)
        if not count:
            continue
        priority = score_priority(
            complaint.title,
            complaint.description,
            complaint.category,
            duplicate_count=count,
            has_image=False,
            has_location=True,
            config=current_app.config,
        )
        complaint.priority_score = priority["score"]
        complaint.priority_level = priority["level"]
        complaint.priority_explanation = priority["explanation"]
        complaint.priority_factors = json.dumps(priority["factors"])
        db.session.add(
            ActivityLog(
                complaint_id=complaint.id,
                event_type="duplicate_scan",
                message=f"{count} similar nearby report(s) found during duplicate scan.",
                actor="system",
            )
        )

    db.session.add(AppSetting(key="seed_version", value=SEED_VERSION))
    db.session.commit()

    return {
        "seeded": True,
        "complaints": len(created_complaints),
        "duplicate_links": DuplicateLink.query.count(),
        "message": "Synthetic demo dataset loaded successfully.",
    }
