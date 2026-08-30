/* Tiny BASIC — a small line-numbered BASIC interpreter.
 * Integers only, 26 variables (A-Z), no floats — keeps it small and avoids
 * pulling in uClibc's float printf/scanf machinery on a tiny target.
 *
 * Statements: LET (implicit), PRINT, INPUT, IF..THEN, GOTO, GOSUB, RETURN,
 * FOR..TO..STEP / NEXT, END, REM, LIST, NEW, RUN.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_LINES 512
#define LINE_LEN 128
#define MAX_GOSUB 32
#define MAX_FOR 16

typedef struct
{
    int num;
    char text[LINE_LEN];
} Line;

static Line prog[MAX_LINES];
static int nlines = 0;

static long vars[26];

static int gosub_stack[MAX_GOSUB];
static int gosub_sp = 0;

typedef struct
{
    char var;
    long limit;
    long step;
    int return_line;
} ForFrame;
static ForFrame for_stack[MAX_FOR];
static int for_sp = 0;

static int running = 0;
static int pc = -1; /* index into prog[] of the current line, -1 = immediate mode */

static const char *cur; /* cursor into the statement text being parsed/executed */

static void skip_ws(void) { while (*cur == ' ' || *cur == '\t') cur++; }

static int find_line_index(int num)
{
    int lo = 0, hi = nlines - 1;
    while (lo <= hi)
    {
        int mid = (lo + hi) / 2;
        if (prog[mid].num == num)
            return mid;
        if (prog[mid].num < num)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return -1;
}

static int find_line_or_after(int num)
{
    for (int i = 0; i < nlines; i++)
        if (prog[i].num >= num)
            return i;
    return nlines;
}

static void store_line(int num, const char *text)
{
    int idx = find_line_index(num);
    if (*text == '\0')
    {
        if (idx >= 0)
        {
            memmove(&prog[idx], &prog[idx + 1], (nlines - idx - 1) * sizeof(Line));
            nlines--;
        }
        return;
    }
    if (idx >= 0)
    {
        snprintf(prog[idx].text, LINE_LEN, "%s", text);
        return;
    }
    if (nlines >= MAX_LINES)
    {
        printf("?PROGRAM FULL\n");
        return;
    }
    int at = find_line_or_after(num);
    memmove(&prog[at + 1], &prog[at], (nlines - at) * sizeof(Line));
    prog[at].num = num;
    snprintf(prog[at].text, LINE_LEN, "%s", text);
    nlines++;
}

/* ---- expression evaluator: recursive descent ----
 * expr    := cmp
 * cmp     := add ( ('='|'<'|'>'|'<='|'>='|'<>') add )?
 * add     := mul ( ('+'|'-') mul )*
 * mul     := unary ( ('*'|'/') unary )*
 * unary   := '-' unary | primary
 * primary := NUMBER | VAR | '(' expr ')'
 */
static long parse_expr(void);

static long parse_primary(void)
{
    skip_ws();
    if (*cur == '(')
    {
        cur++;
        long v = parse_expr();
        skip_ws();
        if (*cur == ')')
            cur++;
        return v;
    }
    if (isdigit((unsigned char)*cur))
    {
        long v = 0;
        while (isdigit((unsigned char)*cur))
            v = v * 10 + (*cur++ - '0');
        return v;
    }
    if (isalpha((unsigned char)*cur))
    {
        int v = toupper((unsigned char)*cur) - 'A';
        cur++;
        return vars[v];
    }
    return 0;
}

static long parse_unary(void)
{
    skip_ws();
    if (*cur == '-')
    {
        cur++;
        return -parse_unary();
    }
    return parse_primary();
}

static long parse_mul(void)
{
    long v = parse_unary();
    for (;;)
    {
        skip_ws();
        if (*cur == '*')
        {
            cur++;
            v *= parse_unary();
        }
        else if (*cur == '/')
        {
            cur++;
            long d = parse_unary();
            v = d ? v / d : 0;
        }
        else
            break;
    }
    return v;
}

static long parse_add(void)
{
    long v = parse_mul();
    for (;;)
    {
        skip_ws();
        if (*cur == '+')
        {
            cur++;
            v += parse_mul();
        }
        else if (*cur == '-')
        {
            cur++;
            v -= parse_mul();
        }
        else
            break;
    }
    return v;
}

static long parse_expr(void)
{
    long v = parse_add();
    skip_ws();
    if (*cur == '=' || *cur == '<' || *cur == '>')
    {
        char op1 = *cur++;
        char op2 = 0;
        if (*cur == '=' && (op1 == '<' || op1 == '>'))
            op2 = *cur++;
        else if (*cur == '>' && op1 == '<')
            op2 = *cur++;
        long rhs = parse_add();
        if (op1 == '=')
            return v == rhs;
        if (op1 == '<' && op2 == '=')
            return v <= rhs;
        if (op1 == '>' && op2 == '=')
            return v >= rhs;
        if (op1 == '<' && op2 == '>')
            return v != rhs;
        if (op1 == '<')
            return v < rhs;
        if (op1 == '>')
            return v > rhs;
    }
    return v;
}

static void skip_to_next_stmt(void)
{
    while (*cur && *cur != ':')
        cur++;
    if (*cur == ':')
        cur++;
}

static int word_is(const char *w)
{
    size_t len = strlen(w);
    if (strncasecmp(cur, w, len) != 0)
        return 0;
    if (isalnum((unsigned char)cur[len]))
        return 0;
    cur += len;
    return 1;
}

static void goto_line(int num)
{
    int idx = find_line_index(num);
    if (idx < 0)
    {
        printf("?UNDEFINED LINE %d\n", num);
        running = 0;
        return;
    }
    pc = idx;
}

static void exec_stmt(void); /* forward */

static void do_print(void)
{
    skip_ws();
    if (*cur == '\0' || *cur == ':')
    {
        printf("\n");
        return;
    }
    for (;;)
    {
        skip_ws();
        if (*cur == '"')
        {
            cur++;
            while (*cur && *cur != '"')
                putchar(*cur++);
            if (*cur == '"')
                cur++;
        }
        else
        {
            printf("%ld", parse_expr());
        }
        skip_ws();
        if (*cur == ',' || *cur == ';')
        {
            char sep = *cur++;
            skip_ws();
            if (*cur == '\0' || *cur == ':')
            {
                if (sep == ',')
                    printf("\t");
                return;
            }
            if (sep == ',')
                printf("\t");
            continue;
        }
        break;
    }
    printf("\n");
}

static void do_input(void)
{
    skip_ws();
    if (*cur == '"')
    {
        cur++;
        while (*cur && *cur != '"')
            putchar(*cur++);
        if (*cur == '"')
            cur++;
        skip_ws();
        if (*cur == ';' || *cur == ',')
            cur++;
        skip_ws();
    }
    if (isalpha((unsigned char)*cur))
    {
        int v = toupper((unsigned char)*cur) - 'A';
        cur++;
        char buf[64];
        printf("? ");
        fflush(stdout);
        if (fgets(buf, sizeof(buf), stdin))
            vars[v] = atol(buf);
    }
}

static void do_let(void)
{
    skip_ws();
    if (!isalpha((unsigned char)*cur))
        return;
    int v = toupper((unsigned char)*cur) - 'A';
    cur++;
    skip_ws();
    if (*cur == '=')
        cur++;
    vars[v] = parse_expr();
}

static void do_if(void)
{
    long cond = parse_expr();
    skip_ws();
    word_is("THEN");
    skip_ws();
    if (!cond)
    {
        running = running; /* condition false: skip rest of line */
        cur += strlen(cur);
        return;
    }
    if (isdigit((unsigned char)*cur))
    {
        int n = 0;
        while (isdigit((unsigned char)*cur))
            n = n * 10 + (*cur++ - '0');
        goto_line(n);
        return;
    }
    exec_stmt();
}

static void do_goto(void)
{
    skip_ws();
    int n = 0;
    while (isdigit((unsigned char)*cur))
        n = n * 10 + (*cur++ - '0');
    goto_line(n);
}

static void do_gosub(void)
{
    skip_ws();
    int n = 0;
    while (isdigit((unsigned char)*cur))
        n = n * 10 + (*cur++ - '0');
    if (gosub_sp >= MAX_GOSUB)
    {
        printf("?GOSUB TOO DEEP\n");
        running = 0;
        return;
    }
    gosub_stack[gosub_sp++] = pc + 1;
    goto_line(n);
}

static void do_return(void)
{
    if (gosub_sp == 0)
    {
        printf("?RETURN WITHOUT GOSUB\n");
        running = 0;
        return;
    }
    pc = gosub_stack[--gosub_sp];
}

static void do_for(void)
{
    skip_ws();
    if (!isalpha((unsigned char)*cur))
        return;
    char v = toupper((unsigned char)*cur);
    cur++;
    skip_ws();
    if (*cur == '=')
        cur++;
    long start = parse_expr();
    skip_ws();
    word_is("TO");
    long limit = parse_expr();
    long step = 1;
    skip_ws();
    if (word_is("STEP"))
        step = parse_expr();

    vars[v - 'A'] = start;
    if (for_sp < MAX_FOR)
    {
        for_stack[for_sp].var = v;
        for_stack[for_sp].limit = limit;
        for_stack[for_sp].step = step;
        for_stack[for_sp].return_line = pc + 1;
        for_sp++;
    }
}

static void do_next(void)
{
    skip_ws();
    char v = isalpha((unsigned char)*cur) ? toupper((unsigned char)*cur) : 0;
    if (v)
        cur++;

    if (for_sp == 0)
    {
        printf("?NEXT WITHOUT FOR\n");
        running = 0;
        return;
    }
    ForFrame *f = &for_stack[for_sp - 1];
    vars[f->var - 'A'] += f->step;
    int done = f->step >= 0 ? vars[f->var - 'A'] > f->limit : vars[f->var - 'A'] < f->limit;
    if (done)
        for_sp--;
    else
        pc = f->return_line;
}

static void do_list(void)
{
    for (int i = 0; i < nlines; i++)
        printf("%d %s\n", prog[i].num, prog[i].text);
}

static void do_run(void)
{
    memset(vars, 0, sizeof(vars));
    gosub_sp = 0;
    for_sp = 0;
    if (nlines == 0)
        return;
    pc = 0;
    running = 1;
    while (running && pc >= 0 && pc < nlines)
    {
        int this_pc = pc;
        cur = prog[pc].text;
        while (*cur && running)
        {
            exec_stmt();
            if (*cur == ':')
                cur++;
        }
        if (running && pc == this_pc)
            pc++;
    }
    running = 0;
}

static void exec_stmt(void)
{
    skip_ws();
    if (*cur == '\0' || *cur == ':')
        return;

    if (word_is("REM"))
    {
        cur += strlen(cur);
    }
    else if (word_is("PRINT") || word_is("?"))
    {
        do_print();
    }
    else if (word_is("INPUT"))
    {
        do_input();
    }
    else if (word_is("LET"))
    {
        do_let();
    }
    else if (word_is("IF"))
    {
        do_if();
    }
    else if (word_is("GOTO"))
    {
        do_goto();
    }
    else if (word_is("GOSUB"))
    {
        do_gosub();
    }
    else if (word_is("RETURN"))
    {
        do_return();
    }
    else if (word_is("FOR"))
    {
        do_for();
    }
    else if (word_is("NEXT"))
    {
        do_next();
    }
    else if (word_is("END") || word_is("STOP"))
    {
        running = 0;
    }
    else if (word_is("LIST"))
    {
        do_list();
    }
    else if (word_is("NEW"))
    {
        nlines = 0;
    }
    else if (word_is("RUN"))
    {
        do_run();
    }
    else if (isalpha((unsigned char)*cur))
    {
        do_let();
    }
    else
    {
        skip_to_next_stmt();
    }
}

static void run_immediate(const char *text)
{
    static char buf[LINE_LEN];
    snprintf(buf, sizeof(buf), "%s", text);
    cur = buf;
    while (*cur)
    {
        exec_stmt();
        if (*cur == ':')
            cur++;
    }
}

int main(void)
{
    char line[LINE_LEN];
    printf("TINY BASIC for riscv32-nommu-uclibc\n");
    printf("READY\n");
    for (;;)
    {
        if (!fgets(line, sizeof(line), stdin))
            break;
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';
        if (len == 0)
            continue;

        const char *p = line;
        while (*p == ' ')
            p++;
        if (isdigit((unsigned char)*p))
        {
            int num = 0;
            while (isdigit((unsigned char)*p))
                num = num * 10 + (*p++ - '0');
            while (*p == ' ')
                p++;
            store_line(num, p);
        }
        else
        {
            run_immediate(p);
        }
    }
    return 0;
}
