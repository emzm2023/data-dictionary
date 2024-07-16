#!/usr/bin/env python
import psycopg2
import csv
import sys
import argparse

# Function to parse arguments
def get_parser(app):
    parser = argparse.ArgumentParser(prog=app)
    parser.add_argument('--h', dest='host',   default='localhost', help='Postgres host')
    parser.add_argument('--p', dest='port',   default='5432',      help='Postgres port')
    parser.add_argument('--u', dest='user',   default='postgres',  help='Postgres user')
    parser.add_argument('--pw', dest='password',   default='',          help='Postgres password')
    parser.add_argument('--db', dest='dbname', default='postgres',  help='Postgres database name')
    parser.add_argument('--t', dest='title', default='data_dictionary', help='Report title')

    return parser

# Function to connect to PostgreSQL database
def connect_to_db(args):
    try:
        conn = psycopg2.connect(
            dbname=args.dbname,
            user=args.user,
            password=args.password,
            host=args.host,
            port=args.port
        )
        print(f"Connected to database '{args.dbname}'")
        return conn
    except psycopg2.Error as e:
        print(f"Error: Could not connect to database '{args.dbname}'")
        print(e)
        sys.exit(1)

# Function to fetch table information
def fetch_table_info(conn):
    tables_info = []
    try:
        with conn.cursor() as curs:
            # Fetching tables and their descriptions
            curs.execute("""
                SELECT table_name, table_schema
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """)
            tables = curs.fetchall()

            for table in tables:
                table_name = table[0]
                table_schema = table[1]

                # Fetching columns and their descriptions
                curs.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_schema, table_name))
                columns = curs.fetchall()

                columns_with_constraints = []
                for column in columns:
                    column_name = column[0]
                    # Fetching constraints for each column (primary key, foreign key, unique)
                    curs.execute("""
                        SELECT tc.constraint_name, tc.constraint_type
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        WHERE kcu.column_name = %s AND kcu.table_name = %s AND kcu.table_schema = %s
                    """, (column_name, table_name, table_schema))
                    constraints = curs.fetchall()
                    constraints_list = [f"{constraint[0]} ({constraint[1]})" for constraint in constraints]
                    column_with_constraints = list(column) + [", ".join(constraints_list)]
                    columns_with_constraints.append(column_with_constraints)

                tables_info.append({
                    'table_name': table_name,
                    'columns': columns_with_constraints
                })

        return tables_info

    except psycopg2.Error as e:
        print("Error fetching table information:")
        print(e)
        return None

# Function to write data dictionary to CSV
def write_to_csv(tables_info, output_file):
    try:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            current_table = None

            for table_info in tables_info:
                table_name = table_info['table_name']
                columns = table_info['columns']

                if table_name != current_table:
                    if current_table is not None:
                        writer.writerow([])  # Add blank line between tables
                    current_table = table_name
                    writer.writerow(['Table:', f"{table_name}"])  # Add table name as a header
                    writer.writerow([f"Description:"])  # Add table description as a header
                    writer.writerow(['Column Name', 'Data Type', 'Nullable', 'Constraints', 'Description', ''])

                for column in columns:
                    writer.writerow([column[0], column[1], column[2], column[3], ''])

        print(f"Data dictionary successfully exported to '{output_file}'")

    except IOError as e:
        print("Error writing to CSV file:")
        print(e)

parser = get_parser(sys.argv[0])
args = parser.parse_args()
conn = connect_to_db(args)

output_file = args.title + '.csv'

# Fetch table information
if conn is not None:
    tables_info = fetch_table_info(conn)

if tables_info:
    # Write data dictionary to CSV
    write_to_csv(tables_info, output_file)
    conn.close()
else:
    print("Cannot proceed without database connection.")