from datetime import date, datetime, timedelta, timezone
import os
from extensions import db
from models import Role, User, Reading, Streak, Group

def seed_database():
    admin_password = os.environ.get('SEED_ADMIN_PASSWORD')
    member_password = os.environ.get('SEED_MEMBER_PASSWORD')
    if not admin_password or not member_password:
        raise RuntimeError(
            'Set SEED_ADMIN_PASSWORD and SEED_MEMBER_PASSWORD before seeding.'
        )

    db.create_all()

    # Seed Roles
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_role = Role(name='Admin', description='System Administrator with full management access')
        db.session.add(admin_role)

    member_role = Role.query.filter_by(name='Member').first()
    if not member_role:
        member_role = Role(name='Member', description='Regular church member submitting daily readings')
        db.session.add(member_role)

    super_admin_role = Role.query.filter_by(name='Super Admin').first()
    if not super_admin_role:
        super_admin_role = Role(
            name='Super Admin',
            description='Platform administrator with access to all groups'
        )
        db.session.add(super_admin_role)

    db.session.commit()

    # Seed Default Group
    group = Group.query.first()
    if not group:
        group = Group(name='Grace Fellowship Small Group', description='Primary accountability reading group')
        db.session.add(group)
        db.session.commit()

    # Seed Admin User
    admin = User.query.filter_by(email='admin@bible.org').first()
    if not admin:
        admin = User(
            name='A Admin',
            email='admin@bible.org',
            role_id=admin_role.id,
            group_id=group.id
        )
        admin.set_password(admin_password)
        db.session.add(admin)

    # Seed 28 Members matching PDF mockups
    members_data = [
        ("Dennis", "dennis@bible.org", "Romans 8:1-17", True,
         "There is no condemnation for those who are in Christ Jesus. God's love and grace give us freedom from guilt and fear.",
         "I will live in the freedom that Christ has given me and not in guilt. I will trust the Holy Spirit to help me daily.",
         "Thank You Lord for Your grace and for setting me free. Help me to walk in Your Spirit today. Amen."),
        ("Mary", "mary@bible.org", "Psalm 23", True,
         "The Lord is my Shepherd; I lack nothing. He leads me beside quiet waters and restores my soul.",
         "I will rest in God's provision today and not worry about tomorrow.",
         "Lord, thank You for being my shepherd and guiding my path."),
        ("John", "john@bible.org", "", False, "", "", ""),
        ("Grace", "grace@bible.org", "Philippians 4:6-7", True,
         "Do not be anxious about anything, but in every situation, by prayer and petition, present your requests to God.",
         "Whenever I feel worried today, I will pause and pray immediately.",
         "Father, give me Your peace that transcends all understanding."),
        ("Peter", "peter@bible.org", "John 15:1-8", True,
         "I am the vine; you are the branches. If you remain in me and I in you, you will bear much fruit.",
         "I will abide in Christ through prayer and meditation on His word throughout the day.",
         "Jesus, help me remain connected to You so I can produce good fruit."),
        ("Sarah", "sarah@bible.org", "", False, "", "", ""),
        ("Brian", "brian@bible.org", "Proverbs 3:5-6", True,
         "Trust in the Lord with all your heart and lean not on your own understanding; in all your ways submit to him.",
         "I will surrender my daily plans and decisions to the Lord.",
         "Lord, give me wisdom to trust You fully in all my choices."),
        ("Lucy", "lucy@bible.org", "", False, "", "", ""),
        ("Paul", "paul@bible.org", "Galatians 2:20", True,
         "I have been crucified with Christ and I no longer live, but Christ lives in me.",
         "I will yield my will to Christ's guidance today.",
         "Lord Jesus, live Your life through me today."),
        ("Esther", "esther@bible.org", "Esther 4:14", True,
         "And who knows but that you have come to your royal position for such a time as this?",
         "I will step up boldly where God places me.",
         "Lord, give me courage to serve You faithfully."),
        ("David", "david@bible.org", "Psalm 119:105", True,
         "Your word is a lamp for my feet, a light on my path.",
         "I will seek Scripture for guidance in every decision.",
         "Thank You Father for illuminating my steps."),
        ("Hannah", "hannah@bible.org", "", False, "", "", ""),
        ("James", "james@bible.org", "James 1:22", True,
         "Do not merely listen to the word, and so deceive yourselves. Do what it says.",
         "I will actively obey what I read today.",
         "Help me be a doer of Your word, Lord."),
        ("Ruth", "ruth@bible.org", "Ruth 1:16", True,
         "Where you go I will go, and where you stay I will stay. Your people will be my people.",
         "I will practice loyalty and love toward my church community.",
         "Lord, give me a steadfast heart."),
        ("Samuel", "samuel@bible.org", "1 Samuel 3:10", True,
         "Speak, for your servant is listening.",
         "I will listen quietly for God's voice in prayer.",
         "Lord, open my ears to hear Your voice."),
        ("Elizabeth", "elizabeth@bible.org", "", False, "", "", ""),
        ("Joseph", "joseph@bible.org", "Genesis 50:20", True,
         "You intended to harm me, but God intended it for good to accomplish what is now being done.",
         "I will trust God's sovereignty even in tough times.",
         "Thank You Lord that You turn all things for good."),
        ("Rachel", "rachel@bible.org", "Psalm 46:10", True,
         "Be still, and know that I am God.",
         "I will take quiet time today to acknowledge God's power.",
         "Lord, calm my busy heart in Your presence."),
        ("Daniel", "daniel@bible.org", "", False, "", "", ""),
        ("Leah", "leah@bible.org", "Genesis 29:35", True,
         "This time I will praise the Lord.",
         "I will focus my gratitude on God rather than circumstances.",
         "Lord, I offer You my praise today."),
        ("Joshua", "joshua@bible.org", "Joshua 1:9", True,
         "Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go.",
         "I will face challenges with courage knowing God is with me.",
         "Father, fill me with Your divine courage."),
        ("Martha", "martha@bible.org", "", False, "", "", ""),
        ("Caleb", "caleb@bible.org", "Numbers 14:24", True,
         "Because my servant Caleb has a different spirit and follows me wholeheartedly...",
         "I will follow God wholeheartedly without compromise.",
         "Give me a wholehearted spirit, Lord."),
        ("Deborah", "deborah@bible.org", "Judges 5:31", True,
         "May all who love you be like the sun when it rises in its strength.",
         "I will shine God's light through encouragement.",
         "Lord, let Your glory shine through my life."),
        ("Gideon", "gideon@bible.org", "", False, "", "", ""),
        ("Rebecca", "rebecca@bible.org", "Genesis 24:60", True,
         "Our sister, may you increase to thousands upon thousands.",
         "I will pray blessings over my family.",
         "Lord, bless and keep my household."),
        ("Isaac", "isaac@bible.org", "Genesis 26:24", True,
         "Do not be afraid, for I am with you; I will bless you.",
         "I will walk in faith and not fear.",
         "Thank You for Your promise to be with me."),
        ("Miriam", "miriam@bible.org", "", False, "", "", "")
    ]

    today = date.today()

    for name, email, passage, submitted, reflection, application, prayer in members_data:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                name=name,
                email=email,
                role_id=member_role.id,
                group_id=group.id
            )
            user.set_password(member_password)
            db.session.add(user)
            db.session.flush()

        # Add Reading if submitted
        if submitted:
            reading = Reading.query.filter_by(user_id=user.id, reading_date=today).first()
            if not reading:
                reading = Reading(
                    user_id=user.id,
                    group_id=group.id,
                    reading_date=today,
                    passage=passage,
                    reflection=reflection,
                    application=application,
                    prayer=prayer,
                    submitted_at=datetime.now(timezone.utc) - timedelta(hours=3)
                )
                db.session.add(reading)

            # Streak
            streak = Streak.query.filter_by(user_id=user.id).first()
            if not streak:
                streak = Streak(
                    user_id=user.id,
                    current_streak=7,
                    longest_streak=14,
                    last_reading_date=today
                )
                db.session.add(streak)

    db.session.commit()
    print("Database successfully seeded with roles, admin, and 28 members!")
