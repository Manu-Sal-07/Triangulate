"""Hand-written prose for the claim corpus, with its own manifest entries beside it.

The structured documents - claim form, FIR header, repair estimate - are templated,
because real forms are templated. The customer narratives are not: each one is written
separately, in a different voice, because a corpus of nine identically-shaped narratives
makes extraction trivial and makes the whole thing look synthetic (docs/SPEC.md section 7).

Each entry pairs the prose with the fields it contains, as (field, canonical, surface)
triples. The surface string must be a verbatim substring of the prose; the renderer copies
these into eval/manifests/ and eval/verify_corpus.py asserts it. Keeping the prose and its
manifest entries in one place is what stops them drifting apart.
"""

from __future__ import annotations

# field name, canonical value, verbatim surface string as it appears in the prose
FieldTriple = tuple[str, str, str]

NARRATIVES: dict[str, dict[str, object]] = {
    "C01": {
        "title": "Statement of the insured",
        "text": """\
I was driving to work on the morning of 2 March 2026, on Baner Road. Traffic was slow
moving. At around 9.40 am an auto-rickshaw came across from the left lane without
indicating and scraped along the front left side of my car. He did not stop.

Damage is to the front left fender and the left headlamp. The car was drivable so I took
it to the authorised workshop the same afternoon and informed your call centre from there
at about 2.20 pm.

No injuries to anyone. No third party claim as far as I know. My licence and RC are both
current.

Priya Deshmukh
""",
        "fields": [
            ("incident_date", "2026-03-02", "2 March 2026"),
            ("incident_time", "09:40", "9.40 am"),
            ("incident_location", "Baner Road, Pune", "Baner Road"),
            ("damage_location", "front-left", "front left fender"),
            ("intimation_date", "2026-03-02", "the same afternoon"),
            ("intimation_time", "14:20", "2.20 pm"),
            ("insured_name", "Priya Deshmukh", "Priya Deshmukh"),
        ],
    },
    "C02": {
        "title": "Statement of the insured",
        "text": """\
My Activa was parked in the basement of my building as it is every night. I went down on
the morning of 11 February 2026 at about quarter past seven to leave for work and the
bay was empty.

I checked the other levels and asked the watchman, who said he had not seen anyone take
it out. The building has a camera at the ramp but the guard told me it has not been
working for some weeks.

I went to Jayanagar Police Station the same morning and the FIR was registered there
around 11 o'clock, number 0112/2026. I called your helpline before going, at about 9.30.

Both keys are with me. The vehicle was locked and the handle lock was engaged.

Anand Raghavan
""",
        "fields": [
            ("theft_discovery_date", "2026-02-11", "11 February 2026"),
            ("incident_time", "07:15", "quarter past seven"),
            ("fir_number", "0112/2026", "number 0112/2026"),
            ("police_station", "Jayanagar Police Station, Bengaluru South", "Jayanagar Police Station"),
            ("intimation_time", "09:30", "9.30"),
            ("insured_name", "Anand Raghavan", "Anand Raghavan"),
        ],
    },
    "C03": {
        "title": "Statement of the insured",
        "text": """\
I apologise that this happened at an odd hour. My father was admitted to Kilpauk Medical
College Hospital that evening and I had gone there directly from home. I was driving back
on NH-48 near Sriperumbudur when cattle came onto the carriageway from the median. It was
about 2.35 am on 19 January 2026. There is no lighting on that stretch and I had very
little time to react.

The front of the vehicle took the whole impact - bonnet, grille, both headlamps, and the
radiator is pushed in. Coolant was leaking so I did not drive it further. A recovery van
towed it to the Toyota workshop at Poonamallee at first light.

I know the amount is on the higher side. The vehicle is a 2019 Innova Crysta and these are
the workshop's rates, not mine. I have attached their estimate as given to me.

I informed your 24-hour line the same morning, a little after 8.

Lakshmi Narayanan
""",
        "fields": [
            ("incident_date", "2026-01-19", "19 January 2026"),
            ("incident_time", "02:35", "2.35 am"),
            ("incident_location", "NH-48 near Sriperumbudur, Tamil Nadu", "NH-48 near Sriperumbudur"),
            ("damage_location", "front", "The front of the vehicle took the whole impact"),
            ("vehicle_make_model", "Toyota Innova Crysta 2.4 GX (2019)", "2019 Innova Crysta"),
            ("insured_name", "Lakshmi Narayanan", "Lakshmi Narayanan"),
        ],
    },
    "C04": {
        "title": "Statement of the insured",
        "text": """\
I want to record that this was entirely the other driver's fault. I was stopped at the
signal on Ring Road near Lajpat Nagar, in the middle lane, waiting for green, when a
tempo behind me failed to stop and went into the back of my car. He was on the phone. I
have his registration and the police have taken his statement.

It was a Saturday evening, around ten past eight. The boot will not close properly now
and the left tail lamp is broken. There was a lot of arguing at the spot and the police
came after some time, so the FIR was registered the next day, on the 15th, along with
my intimation to you which I did the same morning.

The workshop has looked at it and their estimate is attached.

Farhan Qureshi
""",
        "fields": [
            ("incident_time", "20:10", "around ten past eight"),
            ("incident_location", "Ring Road near Lajpat Nagar, New Delhi", "Ring Road near Lajpat Nagar"),
            ("damage_location", "rear", "went into the back of my car"),
            ("intimation_date", "2026-03-15", "on the 15th"),
            ("insured_name", "Farhan Qureshi", "Farhan Qureshi"),
        ],
    },
    "C05": {
        "title": "Statement of the insured",
        "text": """\
My bike is gone. I parked it outside my building on Shivranjani Cross Road at night as I
always do, chained, and when I came down at ten to seven on 26 February 2026 it was not
there.

I have looked around the whole lane and asked at the two shops on the corner. Nobody saw
anything. I called your helpline the same morning and they told me to send this and the
claim form.

I have not been to the police station yet. I went once and was told the officer who
registers vehicle theft complaints was not available and to come back. I will go again
and send the FIR copy as soon as I have it.

Please tell me if anything else is needed.

Nikhil Patel
""",
        "fields": [
            ("theft_discovery_date", "2026-02-26", "26 February 2026"),
            ("incident_time", "06:50", "ten to seven"),
            ("incident_location", "Street parking outside 12 Shivranjani Cross Road, Ahmedabad", "Shivranjani Cross Road"),
            ("intimation_date", "2026-02-26", "the same morning"),
            ("insured_name", "Nikhil Patel", "Nikhil Patel"),
        ],
    },
    "C06": {
        "title": "Statement of the insured",
        "text": """\
On 21 March 2026 at about 7 pm I was on the service road at Warje coming towards home. A
vehicle ahead of me stopped suddenly without any warning. I braked and turned to the right
to avoid hitting it and the car went into the concrete divider.

The front of the car hit the divider straight on. The bumper is pushed in and the bonnet
is buckled. Nothing came from behind me and nothing hit the back of the car - the road
behind me was clear, which is the only reason there was no second accident.

I called your number from the spot, within the hour. The car was towed to the workshop
that night.

Sunita Kulkarni
""",
        "fields": [
            ("incident_date", "2026-03-21", "21 March 2026"),
            ("incident_time", "19:05", "about 7 pm"),
            ("incident_location", "Mumbai-Bengaluru Highway service road, Warje, Pune", "service road at Warje"),
            ("damage_location", "front", "The front of the car hit the divider straight on"),
            ("insured_name", "Sunita Kulkarni", "Sunita Kulkarni"),
        ],
    },
    "C07": {
        "title": "Statement of the insured",
        "text": """\
On 5 February 2026 at about 11.20 in the morning I was crossing the junction on Tonk Road
with the green signal when a car coming from my right jumped the red and hit me on the
left side.

Both left doors are caved in, the pillar between them is bent, and the wheel on that side
is sitting at an angle - the workshop says the suspension has gone. I could not open the
left doors at all afterwards.

The car is a 2016 Alto. I understand the insured value on my policy is lower than what
the workshop has estimated. I am submitting the estimate as it was given to me and I
accept whatever is payable under the policy.

Intimated to you the same day.

Meera Chauhan
""",
        "fields": [
            ("incident_date", "2026-02-05", "5 February 2026"),
            ("incident_time", "11:20", "about 11.20 in the morning"),
            ("incident_location", "Tonk Road, Jaipur", "Tonk Road"),
            ("damage_location", "left side", "hit me on the left side"),
            ("intimation_date", "2026-02-05", "the same day"),
            ("insured_name", "Meera Chauhan", "Meera Chauhan"),
        ],
    },
    "C08": {
        "title": "Statement of the insured",
        "text": """\
This happened on the morning of 8 April 2026 at around 8.15 on the Seaport-Airport Road
at Kakkanad. I had just dropped a passenger at the Infopark gate - I do a few airport and
office runs in the mornings, the fare was settled on the app - and I was pulling out of
the layby when I misjudged the gap and went into the side of a tempo that was standing
there.

Damage is on the front right - the quarter panel and the headlamp on that side, and the
bumper is scraped. The tempo was stationary and there is no damage to it worth speaking of.

I informed your office the same morning.

Thomas Varghese
""",
        "fields": [
            ("incident_date", "2026-04-08", "8 April 2026"),
            ("incident_time", "08:15", "around 8.15"),
            ("incident_location", "Seaport-Airport Road, Kakkanad, Kochi", "Seaport-Airport Road"),
            ("damage_location", "front-right", "Damage is on the front right"),
            ("vehicle_use", "commercial", "I had just dropped a passenger at the Infopark gate"),
            ("intimation_date", "2026-04-08", "the same morning"),
            ("insured_name", "Thomas Varghese", "Thomas Varghese"),
        ],
    },
    "C09": {
        "title": "Statement of the insured",
        "text": """\
Respected Sir/Madam, I am writing regarding the damage caused to my vehicle by a
two-wheeler at the Indira Nagar junction on Faizabad Road. I was going home from the
office and had stopped at the junction to let the traffic from the right pass, and while I
was standing there a boy on a bike came from the side and hit the rear left of my car and
fell down. This was on February 12, 2026, at approx 6.30 in the evening, or it may have
been a few minutes after, I did not look at the watch immediately.

The boy was not badly hurt, some scrapes on his hand, and people gathered and helped him
up. I took him to the chemist shop nearby myself. Because a crowd had collected we decided
to go to the police station and a report was made two days later on the 14th once the boy's
family also came, they wanted it on record.

The damage on my side is the rear left door and the panel behind it, both dented, and some
paint has come off. There is no damage to the lights.

I intimated the claim on the next day itself, 13th February.

Thanking you,
Rajesh K Singh
""",
        "fields": [
            ("incident_date", "2026-02-12", "February 12, 2026"),
            ("incident_time", "18:30", "approx 6.30 in the evening"),
            ("incident_location", "Faizabad Road near Indira Nagar, Lucknow", "Indira Nagar junction on Faizabad Road"),
            ("damage_location", "rear-left", "hit the rear left of my car"),
            ("fir_date", "2026-02-14", "two days later on the 14th"),
            ("intimation_date", "2026-02-13", "the next day itself, 13th February"),
            ("insured_name", "Rajesh Kumar Singh", "Rajesh K Singh"),
        ],
    },
}


# Officialese for the FIR body. Rendered under a templated header.
FIR_BODIES: dict[str, dict[str, object]] = {
    "C02": {
        "text": """\
On the date and time stated above, the complainant Sri Anand Raghavan, resident of 4th
Block Jayanagar, appeared before this Police Station and lodged a written complaint to the
effect that his two-wheeler bearing registration number KA 05 MJ 8871, a Honda Activa 6G,
which was parked by him in the basement parking area of his residential premises, has been
found missing on the morning of 11.02.2026 at about 0715 hours.

The complainant has stated that the said vehicle was locked and that both keys remain in
his possession. Enquiry made with the security personnel on duty has not yielded any
information. The CCTV installation at the entry ramp is reported to be non-functional.

A case is registered under Section 303(2) of the Bharatiya Nyaya Sanhita, 2023 and taken up
for investigation.
""",
        "fields": [
            ("theft_discovery_date", "2026-02-11", "11.02.2026"),
            ("incident_time", "07:15", "0715 hours"),
            ("vehicle_reg", "KA-05-MJ-8871", "KA 05 MJ 8871"),
            ("insured_name", "Anand Raghavan", "Anand Raghavan"),
        ],
    },
    "C04": {
        "text": """\
The complainant Sri Farhan Qureshi, resident of Lajpat Nagar, New Delhi, has appeared
before this Police Station and stated that on 12.03.2026 at about 2010 hours, while his
motor car bearing registration number DL 8C AF 3092 was stationary at the traffic signal on
Ring Road near Lajpat Nagar, a goods tempo approaching from the rear failed to stop and
struck the said motor car from behind, causing damage to its rear portion.

The complainant has further stated that the driver of the offending vehicle was using a
mobile telephone at the material time. The registration particulars of the offending vehicle
have been furnished by the complainant and the driver thereof has been examined.

No injury to any person has been reported. A case is registered under Section 281 of the
Bharatiya Nyaya Sanhita, 2023 and taken up for investigation.
""",
        "fields": [
            ("incident_date", "2026-03-12", "12.03.2026"),
            ("incident_time", "20:10", "2010 hours"),
            ("vehicle_reg", "DL-8C-AF-3092", "DL 8C AF 3092"),
            ("damage_location", "rear", "causing damage to its rear portion"),
            ("insured_name", "Farhan Qureshi", "Farhan Qureshi"),
        ],
    },
    "C09": {
        "text": """\
The complainant Sri R. K. Singh, resident of Indira Nagar, Lucknow, has appeared before
this Police Station and stated that on 12.02.2026 at about 1830 hours, while his motor car
bearing registration number U.P. 32 DN 6647 was stationary at the Indira Nagar junction on
Faizabad Road, a motorcycle proceeding from the left side came into collision with the rear
left portion of the said motor car, in consequence whereof the rider of the motorcycle
sustained minor abrasions.

The rider has declined medical examination and the parties have stated before this Station
that the matter stands settled between them. The present report is recorded at the instance
of both parties for the purpose of record.

A case is registered under Section 281 of the Bharatiya Nyaya Sanhita, 2023.
""",
        "fields": [
            ("incident_date", "2026-02-12", "12.02.2026"),
            ("incident_time", "18:30", "1830 hours"),
            ("vehicle_reg", "UP-32-DN-6647", "U.P. 32 DN 6647"),
            ("damage_location", "rear-left", "rear left portion"),
            ("insured_name", "Rajesh Kumar Singh", "R. K. Singh"),
        ],
    },
}
