import os
from datetime import datetime, timedelta
import random
import hashlib

curs = None
conn = None

currentUser = ""
loggedIn = False

def get_table_str(table):
    return "p320_13.\"" + table + "\""

"""
    insert_into: converts the arguments you enter into an INSERT SQL statement
    @param table: a string representing the table title
    @param columns: an array of the columns to insert into
    @param values: an array of the values to insert into the columns
    @returns uhh something, idk yet
"""
def insert_into(table, columns, values):
    temp = "INSERT INTO " + table + " ("
    temp += ", ".join(columns)
    temp += ") VALUES ("
    temp += ", ".join(["'"+str(x)+"'" for x in values])
    temp += ");"

    #print(temp)
    curs.execute(temp)
    conn.commit()
    return temp

"""
    delete_from: converts the arguments you enter into an DELETE SQL statement
    @param table: a string representing the table title
    @param condition: a string representing the WHERE condition
    @returns uhh something, idk yet
"""
def delete_from(table, condition):
    table = get_table_str(table)
    temp = "DELETE FROM %s WHERE %s;" %  (table, condition)
    curs.execute(temp)
    conn.commit()

"""
    get_count: converts the arguments you enter into a SELECT COUNT SQL statement
    @param table: a string representing the table title
    @param col: the column to get the count of
    @param condition: a condition for counting if there is one
    @returns uhh something, idk yet
"""
def get_count(table, col, condition=None):
    temp = "SELECT MAX(" + col + ") FROM " + table

    if condition is not None: temp += " WHERE " + condition

    temp += ";"

    curs.execute(temp)
    return curs.fetchall()[0][0]

"""
    select_from: converts the arguments you enter into a SELECT FROM SQL statement
    @param table: a string representing the table title
    @param col: the array of columns to select
    @param condition: a condition for selecting if there is one
    @returns uhh something, idk yet
"""
def select_from(table, col, condition=None, setAs=None):
    temp = "SELECT " + ", ".join(col) + " FROM " + table
    if setAs is not None: temp += " AS " + " AS ".join(setAs)
    if condition is not None: temp += " WHERE " + condition
    
    temp += ";"
    curs.execute(temp)
    return curs.fetchall()


def update_from(table, set, where):
    temp = "UPDATE " + table + " SET " + set + " WHERE " + where + ";"
    curs.execute(temp)
    conn.commit()

"""
    Hashes a password string.
    Returns string of hex character of the hash.
     hashes the password and the inverted bits of every other character
    from a reverse direction version of the string
"""
def hash_password(passwordStr, usernameStr):
    passwordBytes = passwordStr.encode('utf-8')
    saltBytes = usernameStr.encode('utf-8')
    hashPass = hashlib.sha256()
    hashPass.update(passwordBytes)
    hashPass.update(saltBytes)
    return hashPass.hexdigest()

def reccomendations():
    if currentUser == None: return
    # My favorite one but doesn't match the rubric example. This one gets the users top genres and then gets the games
    # that have those genres but are not in the users library and haven't been recommended to the user yet.
    # Then it orders those results by the number of genres they have in common with the user and then sorts by the
    # total playtime of the game. Finally it returns a list of the names of the top 10 reccomendations.
    queryV1 = f"""
    WITH top_genres AS (
        SELECT g.genre_id FROM user_plays up JOIN has_genre g ON up.game_id = g.game_id
        WHERE up.username = '{currentUser}' GROUP BY g.genre_id ORDER BY COUNT(*) DESC
    )
    , matching_games AS (
        SELECT hg.game_id, COUNT(*) AS matching_genres FROM has_genre hg JOIN top_genres tg ON hg.genre_id = tg.genre_id
        LEFT JOIN Recommendations r ON hg.game_id = r.game_id AND r.username = '{currentUser}' WHERE r.game_id IS NULL
        GROUP BY hg.game_id
    )
    SELECT g.name, mg.game_id FROM matching_games mg JOIN user_plays up ON mg.game_id = up.game_id JOIN game g ON mg.game_id = g.game_id
    WHERE mg.game_id NOT IN (SELECT game_id FROM user_plays WHERE username = '{currentUser}')
    GROUP BY mg.game_id, mg.matching_genres, g.name
    ORDER BY mg.matching_genres DESC, SUM(ABS(EXTRACT(EPOCH FROM (up."end" - up.start)))) DESC
    LIMIT 5;
    """

    # This one is based on the rubric example. The example was kind of vague so I tried my best to interpret it.
    # Honestly I don't recommend using it because it's kind of gross.
    # This query is split into four parts:
    #   user_genres: gets the most played genres for the user
    #   user_platforms: gets the platforms the user has
    #   similar_users: gets the users that have genres in common with the current user
    #   recommended_games: gets the games that are not in the user's library and haven't been recommended yet from
    #                      the users that have genres in common with the current user.
    #   Then it returns a list of the names of the top 10 reccomendations.
    queryV2 = f"""
    WITH user_genres AS (
        SELECT g.genre_id FROM user_plays up JOIN has_genre g ON up.game_id = g.game_id WHERE up.username = '{currentUser}'
        GROUP BY g.genre_id ORDER BY COUNT(*) DESC
    ),
    user_platforms AS (
        SELECT platform_id FROM has_platform WHERE username = '{currentUser}'
    ),
    similar_users AS (
        SELECT up.username, COUNT(*) AS common_genres FROM user_plays up JOIN has_genre g ON up.game_id = g.game_id
        JOIN user_genres ug ON g.genre_id = ug.genre_id WHERE up.username != '{currentUser}' GROUP BY up.username
        ORDER BY common_genres DESC
        LIMIT 10
    ),
    recommended_games AS (
        SELECT up.game_id, g.name AS game_name, c.name AS developer_name, p.name AS platform_name,
        AVG(r.stars) AS average_rating, RANK() OVER (ORDER BY COUNT(*) DESC) AS play_history_rank FROM user_plays up
        JOIN similar_users su ON up.username = su.username JOIN game g ON up.game_id = g.game_id
        JOIN develops d ON g.game_id = d.game_id JOIN company c ON d.company_id = c.company_id
        JOIN game_on_platform gp ON g.game_id = gp.game_id JOIN platform p ON gp.platform_id = p.platform_id
        JOIN user_platforms upl ON gp.platform_id = upl.platform_id
        LEFT JOIN user_rates r ON up.game_id = r.game_id
        WHERE up.game_id NOT IN (SELECT game_id FROM user_plays WHERE username = '{currentUser}')
        GROUP BY up.game_id, g.name, c.name, p.name
    )
    SELECT game_name, game_ids
    FROM recommended_games WHERE play_history_rank <= 5;
    """

    
    curs.execute(queryV1)
    test = curs.fetchall()
    
    # Insert the top 10 games into the Recommendations table
    insert_query = "INSERT INTO Recommendations (username, game_id) VALUES (%s, %s)"
    for game in test:
        curs.execute(insert_query, (currentUser, game[1]))

    # Commit the changes to the database
    conn.commit()

    # Print the top 10 games
    count = 1
    for x in test:
        print(str(count) + ": " + x[0])
        count += 1

    return


def month_to_num(month_value):
        return {
            'january':1, 'jan': 1, '1':1,
            'february':2, 'feb': 2, '2':2,
            'march': 3, 'mar': 3, '3':3,
            'april': 4, 'apr': 4, '4':4,
            'may': 5, '5':5,
            'june': 6, 'jun': 6, '6':6,
            'july':7, 'jul': 7, '7':7,
            'august':8, 'aug': 8, '8':8,
            'september': 9, 'sep': 9, '9':9,
            'october':10, 'oct': 10, '10':10,
            'november':11, 'nov': 11, '11':11,
            'december':12, 'dec': 12, '12':12,
        }[month_value]

def create_account(username=None, password=None, first=None, last=None, month=None, day=None, year=None):
    if username == None: username = input('Enter username: ')
    if password == None: password = input('Enter password: ')
    if first == None: first = input('Enter first name: ')
    if last == None: last = input('Enter last name: ')
    if month == None: month = month_to_num(input('Enter month of birth: '))
    if day == None: day = input('Enter day of birth: ')
    if year == None: year = input('Enter year of birth: ')

    print("creating account")
    created = datetime.now().strftime('%Y-%m-%d')
    dob = datetime(int(year), int(month), int(day)).strftime('%Y-%m-%d')

    try:
        insert_into(get_table_str("user"),
                    ["username", "password", "firstname", "lastname", "creationDate", "dob", "lastaccessdate"],
                    [username,
#                        password,
                        hash_password(password, username),
                    first, last, created, dob, created])
    except Exception as ex:
        print(ex)

"""
    create_collection: creates a collection for the current user
    @param colName: the name of the collection to create
"""
def create_collection(colName=None):
    if not loggedIn: 
        return print("Please login first")
    
    if colName == None: colName = input('Enter name of collection: ')
    
    id = str(int(get_count(get_table_str("collections"), "collection_id")) + 1)

    try:
        insert_into(get_table_str("collections"),
                    ["collection_id", "username", "name"],
                    [id, currentUser, colName])
    except Exception as e:
        print(e)

def view_collections():
    if not loggedIn: 
        print("Please login first")
        return
    # get collection names ordered by name
    try:
        names = select_from("collections", ["name"], "username = '" + currentUser + "' ORDER BY name ASC")
        print("number of collections: " + str(len(names)))
        for s in names:
            # get number of games in each collection
            count = select_from("contains_game", ["COUNT('game_id')"],
            "C.name = '%s' AND G.username = '%s'" %(s[0], currentUser),
            ["G INNER JOIN collections", "C ON G.collection_id = C.collection_id"]
            )
            #temp = "SELECT EXTRACT(EPOCH FROM (SUM(C.end - C.start))) FROM contains_game AS G INNER JOIN user_plays AS C ON G.game_id = C.game_id \
            #INNER JOIN collections AS CO ON G.collection_id = CO.collection_id \
            #WHERE C.username IN ('" + currentUser + "') AND CO.name = '" + s[0] + "'"
            time = select_from("contains_game", ["EXTRACT(EPOCH FROM (SUM(C.end - C.start)))"],
            "C.username IN ('%s') AND CO.name = '%s'" %(currentUser, s[0]),
            ["G INNER JOIN user_plays",
             "C ON G.game_id = C.game_id INNER JOIN collections",
             "CO ON G.collection_id = CO.collection_id"
             ]
            )
            print("collection name: " + s[0])
            print("\tnumber of games: " + str(count[0][0]))
            if time[0][0] is not None: print("\tnumber of minutes played: " + str(round(time[0][0]/60,2)))
            else: print("\tnumber of minutes played: 0")

    except Exception as e:
        print(e)
    return

def search_for_game(searchOption=None, searchTerm=None, sort=None, ascordesc=None):
    if searchOption == None: searchOption = input("What are you searching by?\n\t1. Game Name\n\t2. Platform \
                                                  \n\t3. Release Date\n\t4. Developer\n\t5. Price\n\t6. Genre\n")
    if searchTerm == None: searchTerm = input('What are you searching for? ')

    try:
        if searchOption == "1":
            games=select_from("game", ["game_id"], "name LIKE ('" + searchTerm + "%')")
        elif searchOption == "2":
            games=select_from("game_on_platform", ["G.game_id"], "name LIKE ('" + searchTerm + "%')", 
                            ["G INNER JOIN platform",
                            "P ON G.platform_id = P.platform_id"])
        elif searchOption == "3":
            games=select_from("game_on_platform", ["game_id"], "release_date = '" + searchTerm + "'")
            print(games)
        elif searchOption == "4":
            games=select_from("develops", ["D.game_id"], "C.name LIKE ('" + searchTerm + "%')",[
                "D INNER JOIN company",
                "C ON D.company_id = C.company_id"
                ])
        elif searchOption == "5":
            games=select_from("game_on_platform", ["game_id"], "price = (" + searchTerm + ")")
        else:
            games=select_from("has_genre", ["H.game_id"], "G.name LIKE ('" + searchTerm + "%')",[
                "H INNER JOIN genre",
                "G ON H.genre_id = G.genre_id"
            ])
    except Exception as ex:
        print(ex)
    if not games:
        print("not found")
        return
    inCommand = "("
    for i in range(len(games)-1):
        inCommand += str(games[i][0]) + ", "
    inCommand += str(games[len(games)-1][0]) + ")"
    if sort == None: sort = input("How should it be sorted?\n\t1. Game Name\n\t2. Price \
                            \n\t3. Release Year\n\t4. Genre\n")
    if ascordesc == None: ascordesc = input("How should that be sorted?\n\t1. Ascending\n\t2. Descending\n")
    order_by = ["g.name, gp.release_date", "gp.price, g.name, gp.release_date", "gp.release_date, g.name", "gen.name, g.name, gp.release_date"]
    sort_by = ["ASC", "DESC"]
    
    temp = "SELECT g.name, plat.name, c.name, ctwo.name, EXTRACT(EPOCH FROM (SUM(up.end - up.start))), g.esrb, AVG(ur.stars)\
        FROM game AS g JOIN game_on_platform as gp ON g.game_id = gp.game_id \
        JOIN platform AS plat ON gp.platform_id = plat.platform_id \
        JOIN develops as d ON g.game_id = d.game_id\
        JOIN company as c ON c.company_id = d.company_id\
        JOIN publishes as p ON g.game_id = p.game_id\
        JOIN company as ctwo ON ctwo.company_id = p.company_id\
        JOIN user_plays as up ON up.game_id = g.game_id\
        JOIN user_rates as ur ON ur.game_id = g.game_id\
        JOIN has_genre as hg ON hg.game_id = g.game_id \
        JOIN genre as gen ON hg.genre_id = gen.genre_id \
        WHERE g.game_id IN " + inCommand + " \
        GROUP BY g.game_id, d.game_id, p.game_id, up.game_id, ur.game_id, gp.game_id, gp.platform_id, plat.platform_id, \
        c.company_id, d.company_id, ctwo.company_id, p.company_id, g.name, gen.name \
        ORDER BY " + order_by[int(sort)-1] + " " + sort_by[int(ascordesc)-1] + ";"
    curs.execute(temp)
    test = curs.fetchall()
    gamenames = []
    platforms = []
    developers = []
    publishers = []
    playtime = []
    ageRating = []
    starRating = []
    count = 0
    for x in test:
        length = len(gamenames)
        if (x[0] not in gamenames): gamenames.append(x[0])
        # new name
        if (len(gamenames) > length):
            platforms.append([x[1]])
            developers.append([x[2]])
            publishers.append([x[3]])
            playtime.append(x[4])
            ageRating.append(x[5])
            starRating.append(x[6]) 
            count += 1
        else:
            if (x[1] not in platforms[count-1]): platforms[count-1].append(x[1])
            if (x[2] not in developers[count-1]): developers[count-1].append(x[2])
            if (x[3] not in publishers[count-1]): publishers[count-1].append(x[3])
    count = 0
    for name in gamenames:
        print("\nname: " + name.upper())
        print("platforms: ", end="")
        print(platforms[count])
        print("developers: ", end="")
        print(developers[count])
        print("publishers: ", end="")
        print(publishers[count])
        print("playtime in hours: " + str(round(playtime[count]/60/60,2)))
        print("ESRB Rating: " + str(ageRating[count]))
        print("Star Rating: " + str(round(starRating[count],2)))
        count += 1
    return

def sort_by_attribute():
    pass

def add_to_collection(gameName=None, collectionName=None):
    if not loggedIn: 
        print("Please login first")
        return
    if gameName == None: gameName = input('What game would you like to add? ')
    
    try:
        gameID = select_from("game", ["game_id"], "name IN ('" + gameName + "')")[0][0]
        temp = "SELECT platform_id FROM has_platform WHERE username = '" + currentUser + "' INTERSECT SELECT platform_id FROM game_on_platform WHERE game_id = " + str(gameID)
        curs.execute(temp)
        platformsGameIsOnThatUserHas = curs.fetchall()
        if not platformsGameIsOnThatUserHas:
            print("WARNING!!!!!! You do not have the platform to play that game on :(")
        if collectionName == None: collectionName = input('What collection would you like to add to? ')
        collectionID = select_from("collections", ["collection_id"], "name IN ('" + collectionName + "') AND username = '" + currentUser + "'")[0][0]
        insert_into("contains_game",
                    ["collection_id", "game_id", "username"],
                    [collectionID, gameID, currentUser])
    except Exception as ex:
        print(ex)


def remove_from_collection(gameName=None, collectionName=None):
    if not loggedIn: 
        print("Please login first")
        return
    
    if collectionName == None: collectionName = input('what collection would you like to modify? ')
    if gameName == None: gameName = input('What game would you like to remove? ')
    
    try:
        gameID = select_from("game", ["game_id"], "name='"+gameName+"'")
        collectionID = select_from("collections", ["collection_id"],
                        "name='%s' AND username='%s'"
                        %(collectionName,currentUser))
        
        gameID = gameID[0][0]
        collectionID = collectionID[0][0]

        delete_from("contains_game",
                    "collection_id='%s' AND game_id='%s' AND username='%s'"
                    %(collectionID, gameID, currentUser))
    except Exception as e:
        print(e)

    return

def rename_collection(oldName=None, newName=None):
    if not loggedIn: 
        print("Please login first")
        return
    if oldName == None: oldName = input('Enter collection name you want to change: ')
    if newName == None: newName = input('Enter the new name: ')
    update_from(get_table_str("collections"), "name = ('" + newName + "')", "name IN ('" + oldName + "') AND username = '" + currentUser + "'")

def delete_collection(name=None):
    if not loggedIn: 
        print("Please login first")
        return
    if name == None: name = input('Enter name of collection to delete: ')
    try:
        collectionID = select_from("collections", ["collection_id"], "name IN ('" + name + "') AND username = '" + currentUser + "'")[0][0]
        delete_from("contains_game", "collection_id = " + str(collectionID))
        delete_from("collections", "collection_id = " + str(collectionID))
    except Exception as e:
        print(e)
    

def rate_game(name=None, stars=None):
    if not loggedIn: 
        print("Please login first")
        return
    if name == None: name = input('Which game would you like to rate? ')
    if stars == None: stars = input('What would you rate it (1-5)? ')
    try:
        gameID = select_from("game", ["game_id"], "name IN ('" + name + "')")[0][0]
    except:
        print("not a game")
    try:
        temp = "SELECT username FROM (SELECT username FROM user_rates WHERE game_id = " + str(gameID) + ") AS FOO WHERE username = '" + currentUser + "'"
        curs.execute(temp)
        hasUserAlreadyRated = curs.fetchall()
    except Exception as e:
        print(e)
    if (not hasUserAlreadyRated): 
        insert_into("user_rates",
                    ["username", "game_id", "stars"],
                    [currentUser, gameID, stars])
    else:
        update_from(get_table_str("user_rates"), "stars = " + str(stars) + "", "username IN ('" + currentUser + "') AND game_id = " + str(gameID))
    pass

def play_game(game=None, playtime=None):
    if not loggedIn: 
        print("Please login first")
        return
    question = input("Do you want to play a random game from your collection? (Yes/No)")
    if question == "Yes":
        collTable = get_table_str("collections")
        contGameTable = get_table_str("contains_game")
        query = f"SELECT * FROM {collTable} as c INNER JOIN {contGameTable} as cg ON c.collection_id = cg.collection_id WHERE c.username = '{currentUser}'"
        curs.execute(query)
        randGId = random.choice(curs.fetchall())[4]
        game = select_from(get_table_str("game"), "*", f"game_id = '{randGId}'")[0]
        print(f"You will play {game[2]} from your collection.")
        if playtime == None: playtime = input("How long did you play? (HH:MM): ")

        try:
            playtime = playtime.split(":")
            if len(playtime) == 2:
                start = (datetime.now() - timedelta(hours=int(playtime[0]), minutes=int(playtime[1]))).strftime("%Y/%m/%d %H:%M:%S")
                end = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                print("start: %s\nend: %s" % (start, end))
                insert_into(get_table_str("user_plays"),
                    ["username", "game_id", "start", '"end"'],
                    [currentUser, game[0], start, end])
        except Exception as e:
            print(e)
    else :
        if game == None: game = input("What game did you play?: ")
        if playtime == None: playtime = input("How long did you play? (HH:MM): ")

        try:
            playtime = playtime.split(":")
            if len(playtime) == 2:
                start = (datetime.now() - timedelta(hours=int(playtime[0]), minutes=int(playtime[1]))).strftime("%Y/%m/%d %H:%M:%S")
                end = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

                print("start: %s\nend: %s" % (start, end))

                gameID = select_from("game", ["game_id"],
                    "name='%s'" % game)[0][0]
                print("%s: %d" %(game, gameID))
                insert_into(get_table_str("user_plays"),
                    ["username", "game_id", "start", '"end"'],
                    [currentUser, gameID, start, end]
                )
        except Exception as e:
            print(e)


def follow_friend(username=None):
    if not loggedIn: 
        print("Please login first")
        return
    if username == None: username = input('Name of friend to follow: ')
    try:
        alreadyFriends = select_from("friends", ["friender_username"], "friender_username = '" + currentUser + "' AND friendee_username = '" + username + "'")
    except Exception as e:
        print(e)
    if not alreadyFriends:
        insert_into("friends",
                    ["friender_username", "friendee_username"],
                    [currentUser, username])
    else:
        print("you already follow that person")
    pass

def unfollow_friend(username=None):
    if not loggedIn: 
        print("Please login first")
        return
    if username == None: username = input('Name of friend to unfollow: ')
    try:
        alreadyFriends = select_from("friends", ["*"], "friender_username = '" + currentUser + "' AND friendee_username = '" + username + "'")
    except Exception as e:
        print(e)
    if alreadyFriends:
        delete_from("friends", "friender_username = '" + currentUser + "' AND friendee_username = '" + username + "'")
    else:
        print("you do not follow that person")
    pass

def search_for_friend(email=None):
    if not loggedIn: 
        print("Please login first")
        return
    if email == None: email = input('Email of friend: ')
    try:
        user = select_from(get_table_str("emails"), ["username"], "email='" + email + "'")
        print("Username: " + user[0][0])
    except Exception as e:
        print(e)

def login():
    username = input('Enter username: ')
    password = input('Enter password: ')

#    if password == str(select_from(get_table_str("user"), ["password"], "username='" + username + "'")[0][0]):
    if hash_password(password,username) == str(select_from(get_table_str("user"), ["password"], "username='" + username + "'")[0][0]):
        global currentUser, loggedIn
        currentUser = username
        loggedIn = True
        lastAccess = datetime.now().strftime('%Y-%m-%d')
        update_from(get_table_str("user"), "lastaccessdate = '" + lastAccess + "'", "username='" + username + "'")
    else: 
        print("Log in failed. Please check your username and password")

def follow_count():
    if not loggedIn: 
        print("Please login first")
        return
    try:
        followerCount = select_from(get_table_str("friends"), ["COUNT(friendee_username)"], "friendee_username='" + currentUser + "'")[0][0]
        followingCount = select_from(get_table_str("friends"), ["COUNT(friender_username)"], "friender_username='" + currentUser + "'")[0][0]
    except Exception as e:
        print(e)
    print("Followers: " + str(followerCount))
    print("Following: " + str(followingCount))

def my_top_ten_games(rankMethod = None):
    if not loggedIn: 
        print("Please login first")
        return
    if rankMethod == None: rankMethod = input("What are you ranking your games by?\n\t1. Star Rating\n\t2. Playtime \
                                                  \n\t3. Star Rating then Playtime\n")
    if (rankMethod == "1"):
        temp = "SELECT g.name FROM user_rates as U \
                INNER JOIN game g on g.game_id = U.game_id \
                WHERE U.username='" + currentUser + "' \
                GROUP BY U.game_id, U.stars, g.game_id \
                ORDER BY U.stars DESC \
                LIMIT 10"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1
    if (rankMethod == "2"):
        temp = "SELECT g.name FROM user_plays as U \
                INNER JOIN game g on g.game_id = U.game_id \
                WHERE U.username='" + currentUser + "' \
                GROUP BY U.game_id, g.game_id \
                ORDER BY EXTRACT(EPOCH FROM (SUM(U.end-U.start))) DESC \
                LIMIT 10"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1
    if (rankMethod == "3"):
        temp = "SELECT g.name FROM user_plays as U \
                INNER JOIN game g on g.game_id = U.game_id \
                JOIN user_rates r on g.game_id = r.game_id \
                WHERE U.username='" + currentUser + "' AND r.username='" + currentUser + "' \
                GROUP BY U.game_id, g.game_id, r.stars \
                ORDER BY r.stars DESC, EXTRACT(EPOCH FROM (SUM(U.end-U.start))) DESC \
                LIMIT 10"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1

def what_is_popular(rankMethod = None):
    if rankMethod == None: rankMethod = input("What would you like to see?\n\t1. What's popular in the last 90 days?\n\t2. What's new with my friends? \
                                                  \n\t3. What's new this month?\n")
    if (rankMethod == "1"):
        temp = "SELECT g.name FROM user_plays as U \
                INNER JOIN game g on g.game_id = U.game_id \
                WHERE U.end::date > (current_date - 90) AND U.start::date > (current_date - 90) \
                GROUP BY U.game_id, g.game_id \
                ORDER BY EXTRACT(EPOCH FROM (SUM(U.end-U.start))) DESC \
                LIMIT 20"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1
    if (rankMethod == "2"):
        if not loggedIn: 
            print("Please login first")
            return
        temp = "SELECT g.name FROM user_plays as U \
                INNER JOIN game g on g.game_id = U.game_id \
                INNER JOIN friends f on f.friendee_username = U.username \
                WHERE f.friendee_username IN (SELECT friendee_username FROM friends WHERE friender_username = '" + currentUser + "') \
                    AND U.end::date > (current_date - 90) AND U.start::date > (current_date - 90) \
                GROUP BY U.game_id, g.game_id \
                ORDER BY EXTRACT(EPOCH FROM (SUM(U.end-U.start))) DESC \
                LIMIT 20"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1
    if (rankMethod == "3"):
        temp = "SELECT g.name FROM user_plays as U \
                INNER JOIN game g on g.game_id = U.game_id \
                INNER JOIN game_on_platform gop on g.game_id = gop.game_id \
                WHERE EXTRACT(month from gop.release_date::date) = EXTRACT(month from current_date) \
                AND EXTRACT(year from gop.release_date::date) = EXTRACT(year from current_date) \
                AND EXTRACT(month from U.end::date) = EXTRACT(month from current_date) \
                AND EXTRACT(year from U.end::date) = EXTRACT(year from current_date) \
                GROUP BY U.game_id, g.game_id \
                ORDER BY EXTRACT(EPOCH FROM (SUM(U.end-U.start))) DESC \
                LIMIT 5"
        curs.execute(temp)
        test = curs.fetchall()
        count = 1
        for x in test:
            print(str(count) + ": " + x[0])
            count += 1


'''
    print commands available to the user
'''
def help():
    print("\nCommands:")
    for comVals in command_blueprints:
        cb_val = command_blueprints[comVals]
        ### format function name to spaced title format
        print(f" {cb_val[-1]:>2}) "+' '.join(comVals.__name__.split("_")).title(),end=":")
        for counted, comOpt in enumerate(cb_val[:-1]):
            if counted != 0: print(end=' '*(6+len(comVals.__name__)))
            print(f" - \"{comOpt}\"")
        if len(cb_val)==0: print()
    print(" Quit: - \"quit\" (or leave empty)")

'''
    will be reversed into the commands dictionary by setup_commands()
    format for each entry:
        function for command : [array of keywords to access that function]
    the last keyword will not be displayed in the printed options,
        but instead will be printed as the number of the command,
        therefore it should be a number, and one that is not used
        just follow the counting order that should already be there
'''
command_blueprints = {
    help : ["help", "0"],
    create_account : ["create_account","1"],
    create_collection : ["create_collection","2"],
    view_collections : ["view_collections","3"],
    search_for_game : ["search_for_game","4"],
    add_to_collection : ["add_to_collection","5"],
    remove_from_collection : ["remove_from_collection","6"],
    rename_collection : ["rename_collection","7"],
    delete_collection : ["delete_collection","8"],
    rate_game : ["rate_game","9"],
    play_game : ["play_game","10"],
    follow_friend : ["follow_friend","11"],
    unfollow_friend : ["unfollow_friend","12"],
    search_for_friend : ["search_for_friend","13"],
    login : ["login","14"],
    follow_count : ["follow_count","15"],
    my_top_ten_games : ["my_top_ten_games","16"],
    reccomendations : ["reccomendations","17"],
    what_is_popular : ["what_is_popular","18"]
}
commands = {}

'''
    builds commands dictionary by reversing command_blueprints
    returns True for utilization by command_branch()
'''
def setup_commands():
    for func in command_blueprints:
        for text_option in command_blueprints[func]:
            commands[text_option] = func
    return True

'''
    command_branch() function
        connects text-entered commands to their functions
        utilizes command_blueprints and commands dictionaries
        utilizes setup_commands() function as default value
            to ensure that commands dictionary is filled
    
    parameters:
        _curs
            copied to global 'curs'
        _cons
            copied to global 'cons'
        clear_screen
            determines if "cls" is run in command line
            defaults to True
'''
def command_branch(_curs, _conn, clear_screen=setup_commands()):
    global curs, conn
    curs = _curs
    conn = _conn
    if clear_screen: os.system("cls")
    help()
    quit = False
    while (not quit):
        comEntry = input("Enter a command: ")
        if comEntry.lower() in ["quit",""]: quit = True
        elif comEntry not in commands: print("invalid command")
        else: commands[comEntry]()
    return print("goodbye!")

if __name__=="__main__":
    command_branch() # doesn't work anymore (no curs, no conn)