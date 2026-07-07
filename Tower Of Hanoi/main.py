def hanoi_solver(n):
    rods = {1: list(range(n, 0, -1)), 2: [], 3: []}

    def state_str():
        return " ".join(str(rods[i]) for i in (1, 2, 3))

    moves = [state_str()]

    def move(k, src, aux, dst):
        if k == 0:
            return
        move(k - 1, src, dst, aux)
        disk = rods[src].pop()
        rods[dst].append(disk)
        moves.append(state_str())
        move(k - 1, aux, src, dst)

    move(n, 1, 2, 3)
    return "\n".join(moves)
