# Staff guide / Mwongozo wa wafanyakazi

## English

1. Open `/staff/` and sign in with the staff account created for you. Sign out on shared devices.
2. Dispatchers and admin assistants use **Customer map** and **Registered customers** to find and edit customer records, copy coordinates, and open map directions. Admin assistants can view customer-key history but cannot issue keys or create staff accounts.
3. Service providers open **Customer keys** to issue a reusable key for a customer's phone. Search/filter your own issued keys and give the key to the matching customer. Choose **Revoke** in the key row and confirm to disable a key immediately. Copy a new key when it is shown; the secret cannot be retrieved later. The key works until its expiry or revocation.
4. Customers open the public map's hamburger menu or **Customer sign in / register**, then enter the phone and key. A new phone proceeds to registration. A known phone loads its saved details and location so the customer can update them.
5. Only the superuser can create admin assistants and service-provider accounts. Admin assistants cannot create other staff accounts or issue customer keys. Providers can issue keys but cannot access the customer directory. The superuser and admin assistants can review audit history and export data.
6. Use **Navigate · Google Maps** or another map app from a customer record. The link carries coordinates only. Call the customer before travelling when location confidence is low. Pin corrections are recorded with the staff account and time.

**Security status:** MFA enrollment and recovery are not implemented yet. Use only controlled testing accounts and do not handle routine real customer records until the owner completes the MFA release gate. The Django `/admin/` site is restricted to superusers; the normal staff API/dashboard is the intended workspace.

## Kiswahili

1. Fungua `/staff/` na uingie kwa akaunti uliyopewa. Toka kwenye akaunti ukitumia kifaa cha pamoja.
2. Dispatchers na wasaidizi wa admin hutumia **Customer map** na **Registered customers** kutafuta na kusahihisha taarifa za wateja, kunakili viwianishi na kufungua ramani ya maelekezo. Wasaidizi wa admin wanaweza kuona historia ya funguo za wateja lakini hawawezi kutoa funguo wala kuunda akaunti za wafanyakazi.
3. Watoa huduma hufungua **Customer keys** kutoa ufunguo unaoweza kutumika tena kwa simu ya mteja. Tafuta au chuja funguo ulizotoa na umpe ufunguo mteja mwenye simu inayolingana. Bonyeza **Revoke** kwenye mstari wa ufunguo na uthibitishe ili kuuzima mara moja. Unapoonyeshwa, nakili ufunguo mpya; hauwezi kuonekana tena. Utaendelea kufanya kazi hadi muda wake uishe au uzuiwe.
4. Mteja afungue menyu ya mistari mitatu kwenye ramani ya umma au **Customer sign in / register**, kisha aweke simu na ufunguo. Simu mpya itaendelea kwenye usajili. Simu iliyosajiliwa itaonyesha taarifa na eneo lililohifadhiwa ili mteja aweze kusasisha.
5. Superuser pekee ndiye anayeweza kuunda akaunti za wasaidizi wa admin na watoa huduma. Wasaidizi hawawezi kuunda wafanyakazi wengine wala kutoa funguo za wateja. Watoa huduma wanaweza kutoa funguo lakini hawawezi kuona orodha ya wateja. Superuser na wasaidizi wa admin wanaweza kuona historia ya ukaguzi na kupakua data.
6. Tumia **Navigate · Google Maps** au programu nyingine ya ramani kwenye rekodi ya mteja. Kiungo hutuma viwianishi pekee. Mpigie mteja kuthibitisha ikiwa eneo halina uhakika. Marekebisho ya pini huhifadhiwa pamoja na akaunti ya mfanyakazi na muda.

**Hali ya usalama:** MFA na urejeshaji wa akaunti bado havijatekelezwa. Tumia akaunti za majaribio pekee; usihudumie rekodi halisi za wateja kwa matumizi ya kawaida hadi mmiliki amalize sharti la MFA. Tovuti ya Django `/admin/` imewekewa superuser pekee; dashibodi ya wafanyakazi ndiyo sehemu ya kawaida ya kazi.
