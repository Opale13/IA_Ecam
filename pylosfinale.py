#!/usr/bin/env python3
# pylos.py
# Author: Quentin Lurkin
# Version: April 28, 2017
# -*- coding: utf-8 -*-

import argparse
import socket
import sys
import json
import ast
import copy
from lib import game


class PylosState(game.GameState):
    '''Class representing a state for the Pylos game.'''

    def __init__(self, initialstate=None):

        if initialstate == None:
            # define a layer of the board
            def squareMatrix(size):
                matrix = []
                for i in range(size):
                    matrix.append([None] * size)
                return matrix

            board = []
            for i in range(4):
                board.append(squareMatrix(4 - i))

            initialstate = {
                'board': board,
                'reserve': [15, 15],
                'turn': 0
            }

        super().__init__(initialstate)

    def get(self, layer, row, column):
        '''Permet de savoir si les coord sont bonnes et si la place est libre'''
        if layer < 0 or row < 0 or column < 0:
            raise game.InvalidMoveException('The position ({}) is outside of the board'.format([layer, row, column]))
        try:
            # return None si vide, 1 ou 0 en fonction du joueur
            return self._state['visible']['board'][layer][row][column]
        except:
            raise game.InvalidMoveException('The position ({}) is outside of the board'.format([layer, row, column]))

    def safeGet(self, layer, row, column):
        try:
            return self.get(layer, row, column)
        except game.InvalidMoveException:
            return None

    def validPosition(self, layer, row, column):
        '''permet de savoir si la place est libre et si elle est stable'''
        if self.get(layer, row, column) != None:
            raise game.InvalidMoveException('The position ({}) is not free'.format([layer, row, column]))

        if layer > 0:
            if (
                                    self.get(layer - 1, row, column) == None or
                                    self.get(layer - 1, row + 1, column) == None or
                                self.get(layer - 1, row + 1, column + 1) == None or
                            self.get(layer - 1, row, column + 1) == None
            ):
                raise game.InvalidMoveException('The position ({}) is not stable'.format([layer, row, column]))

    def canMove(self, layer, row, column):
        '''Verifie si la place est vide, et s'il y a une piéce au dessus'''
        if self.get(layer, row, column) == None:
            raise game.InvalidMoveException('The position ({}) is empty'.format([layer, row, column]))

        if layer < 3:
            if (
                                    self.safeGet(layer + 1, row, column) != None or
                                    self.safeGet(layer + 1, row - 1, column) != None or
                                self.safeGet(layer + 1, row - 1, column - 1) != None or
                            self.safeGet(layer + 1, row, column - 1) != None
            ):
                raise game.InvalidMoveException('The position ({}) is not movable'.format([layer, row, column]))

    def createSquare(self, coord):
        '''Regarde si on a créé une carré'''
        layer, row, column = tuple(coord)

        def isSquare(layer, row, column):
            if (
                                    self.safeGet(layer, row, column) != None and
                                    self.safeGet(layer, row + 1, column) == self.safeGet(layer, row, column) and
                                self.safeGet(layer, row + 1, column + 1) == self.safeGet(layer, row, column) and
                            self.safeGet(layer, row, column + 1) == self.safeGet(layer, row, column)
            ):
                return True
            return False

        if (
                            isSquare(layer, row, column) or
                            isSquare(layer, row - 1, column) or
                        isSquare(layer, row - 1, column - 1) or
                    isSquare(layer, row, column - 1)
        ):
            return True
        return False

    def set(self, coord, value):
        layer, row, column = tuple(coord)
        self.validPosition(layer, row, column)
        self._state['visible']['board'][layer][row][column] = value

    def remove(self, coord, player):
        layer, row, column = tuple(coord)
        self.canMove(layer, row, column)
        sphere = self.get(layer, row, column)
        if sphere != player:
            raise game.InvalidMoveException('not your sphere')
        self._state['visible']['board'][layer][row][column] = None

    # update the state with the move
    # raise game.InvalidMoveException
    def update(self, move, player):
        state = self._state['visible']
        if move['move'] == 'place':
            if state['reserve'][player] < 1:
                raise game.InvalidMoveException('no more sphere')
            self.set(move['to'], player)
            state['reserve'][player] -= 1
        elif move['move'] == 'move':
            if move['to'][0] <= move['from'][0]:
                raise game.InvalidMoveException('you can only move to upper layer')
            sphere = self.remove(move['from'], player)
            try:
                self.set(move['to'], player)
            except game.InvalidMoveException as e:
                self.set(move['from'], player)
                raise e
        else:
            raise game.InvalidMoveException('Invalid Move:\n{}'.format(move))

        if 'remove' in move:
            if not self.createSquare(move['to']):
                raise game.InvalidMoveException('You cannot remove spheres')
            if len(move['remove']) > 2:
                raise game.InvalidMoveException('Can\'t remove more than 2 spheres')
            for coord in move['remove']:
                sphere = self.remove(coord, player)
                state['reserve'][player] += 1

        state['turn'] = (state['turn'] + 1) % 2

    # return 0 or 1 if a winner, return None if draw, return -1 if game continue
    def winner(self):
        state = self._state['visible']
        if state['reserve'][0] < 1:
            return 1
        elif state['reserve'][1] < 1:
            return 0
        return -1

    def val2str(self, val):
        return '_' if val == None else '@' if val == 0 else 'O'

    def player2str(self, val):
        return 'Light' if val == 0 else 'Dark'

    def printSquare(self, matrix):
        print(' ' + '_' * (len(matrix) * 2 - 1))
        print('\n'.join(map(lambda row: '|' + '|'.join(map(self.val2str, row)) + '|', matrix)))

    # print the state
    def prettyprint(self):
        state = self._state['visible']
        for layer in range(4):
            self.printSquare(state['board'][layer])
            print()

        for player, reserve in enumerate(state['reserve']):
            print('Reserve of {}:'.format(self.player2str(player)))
            print((self.val2str(player) + ' ') * reserve)
            print()

        print('{} to play !'.format(self.player2str(state['turn'])))
        # print(json.dumps(self._state['visible'], indent=4))


class PylosServer(game.GameServer):
    '''Class representing a server for the Pylos game.'''

    def __init__(self, verbose=False):
        super().__init__('Pylos', 2, PylosState(), verbose=verbose)

    def applymove(self, move):
        try:
            self._state.update(json.loads(move), self.currentplayer)
        except json.JSONDecodeError:
            raise game.InvalidMoveException('move must be valid JSON string: {}'.format(move))


class PylosClient(game.GameClient):
    '''Class representing a client for the Pylos game.'''

    def __init__(self, name, server, verbose=False):
        super().__init__(server, PylosState, verbose=verbose)
        self.__name = name

    def _handle(self, message):
        pass

    # return move as string
    def _nextmove(self, state):
        difficultée = 1
        a = ast.literal_eval(str(state).replace("null", "None"))

        def get(a, layer, row, column):
            '''Permet de savoir si les coord sont bonnes et si la place est libre'''
            if layer < 0 or row < 0 or column < 0:
                raise Exception('My error!')
            try:
                # return None si vide, 1 ou 0 en fonction du joueur
                return a['board'][layer][row][column]
            except:
                raise Exception('My error!')

        def validPosition(a, layer, row, column):
            '''permet de savoir si la place est libre et si elle est stable'''
            if get(a, layer, row, column) != None:
                raise Exception('My error!')

            if layer > 0:
                if (
                                        get(a, layer - 1, row, column) == None or
                                        get(a, layer - 1, row + 1, column) == None or
                                    get(a, layer - 1, row + 1, column + 1) == None or
                                get(a, layer - 1, row, column + 1) == None
                ):
                    raise Exception('My error!')

        def safeGet(a, layer, row, column):
            try:
                return get(a, layer, row, column)
            except:
                return None

        def canMove(a, layer, row, column):
            if get(a, layer, row, column) == None:
                raise Exception('My error!')
            if layer < 3:
                if (
                                        safeGet(a, layer + 1, row, column) != None or
                                        safeGet(a, layer + 1, row - 1, column) != None or
                                    safeGet(a, layer + 1, row - 1, column - 1) != None or
                                safeGet(a, layer + 1, row, column - 1) != None
                ):
                    raise Exception('My error!')

        def remove(a, coord, player):
            layer, row, column = tuple(coord)
            canMove(a, layer, row, column)
            sphere = get(a, layer, row, column)
            if sphere != player:
                raise Exception('My error!')
            a['board'][layer][row][column] = None

        def coupspossiblesajouter(a):
            libre = []
            nonvalide = []
            for layer in range(4):
                for row in range(4 - layer):
                    for column in range(4 - layer):
                        if get(a, layer, row, column) is None:
                            libre += [(layer, row, column)]
            for i in libre:
                try:
                    validPosition(a, i[0], i[1], i[2])
                except:
                    nonvalide += [i]
            for i in nonvalide:
                libre.remove(i)
            return libre

        def coupspossiblesbouger(a, player=a["turn"]):
            canmove = []
            for layer in range(4):
                for row in range(4 - layer):
                    for column in range(4 - layer):
                        try:
                            canMove(a, layer, row, column)
                            canmove += [(layer, row, column)]
                        except:
                            pass
            coup = {}
            for i in canmove:
                if len(canmove) > 0:
                    try:
                        copiestate = copy.deepcopy(a)
                        remove(copiestate, i, player)

                        coup[i] = coupspossiblesajouter(copiestate)
                        coup[i].remove(i)

                        liste = []
                        for d in coup[i]:
                            if d[0] <= i[0]:
                                liste += [d]
                        for elements in liste:
                            coup[i].remove(elements)
                    except:
                        pass
            liste = []
            for i in coup:
                if len(coup[i]) == 0:
                    liste += [i]
            for i in liste:
                del coup[i]
            return coup

        def uncarre(a, coord, player=a["turn"]):
            carrépossible = []
            coordonnée = []
            for layer in range(3):
                for row in range(3 - layer):
                    for column in range(3 - layer):
                        # print(a["board"][layer][row][column])
                        carrépossible += [[a["board"][layer][row][column], a["board"][layer][row][column + 1],
                                           a["board"][layer][row + 1][column],
                                           a["board"][layer][row + 1][column + 1]]]
                        coordonnée += [[[layer, row, column], [layer, row, column + 1],
                                        [layer, row + 1, column], [layer, row + 1, column + 1]]]
            # return carrépossible
            for i in coordonnée:
                if coord in i:
                    if carrépossible[coordonnée.index(i)] == [player, player, player, player]:
                        return True, i
            return False, coord

        def removable(a, player):
            liste = []
            for layer in range(4):
                for row in range(4 - layer):
                    for column in range(4 - layer):
                        copie = copy.deepcopy(a)
                        try:
                            remove(copie, [layer, row, column], player)
                            liste += [[layer, row, column]]
                        except:
                            pass
            return liste

        def combinaisons(ar):
            b = []
            for i1 in ar:
                b += [[i1]]
                for i2 in ar:
                    if i1 != i2:
                        if [i2, i1] not in b:
                            b += [[i1, i2]]
            return b

        def ajouter(a, coord, player):
            copiea = copy.deepcopy(a)
            copiea["board"][coord[0]][coord[1]][coord[2]] = player
            copiea["reserve"][player] -= 1
            # return uncarre(copiea, coord, 1)
            # print("ajouter: ", coord, player)
            return copiea

        def deplacer(a, avant, apres, player):
            copiea = copy.deepcopy(a)
            copiea["board"][avant[0]][avant[1]][avant[2]] = None
            copiea["board"][apres[0]][apres[1]][apres[2]] = player
            # print("deplacer: ", avant, apres, player)
            return copiea

        def supprimer(a, coord):
            copiea = copy.deepcopy(a)
            copiea["reserve"][copiea["board"][coord[0]][coord[1]][coord[2]]] += 1
            copiea["board"][coord[0]][coord[1]][coord[2]] = None
            # print("supprimer: ", coord)
            return copiea

        def coups(a, player, donnermouvement="non"):
            listeajouter = []
            listebouger = []
            listemove = []
            # remplacer les 0 par des 1 et inversément en fonction de player
            move = []

            # print("Si on ajoute: ")
            for i in coupspossiblesajouter(a):
                # print(ajouter(a, [i[0], i[1], i[2]], player))
                move += ["{" + "'move': 'place','to': [{},{},{}]".format(i[0], i[1], i[2]) + "}"]

                listemove += [ajouter(a, [i[0], i[1], i[2]], player)]
                listeajouter += [ajouter(a, [i[0], i[1], i[2]], player)]
                copiea = copy.deepcopy(ajouter(a, [i[0], i[1], i[2]], player))
                if uncarre(copiea, [i[0], i[1], i[2]], player)[0] == True:
                    # print(removable(copiea, 1))
                    for i1 in combinaisons(removable(copiea, player)):
                        move += ["{" + "'move': 'place','to': [{},{},{}], ".format(i[0], i[1], i[2]) + \
                                 "'remove': {}".format(i1) + "}"]
                        copiecopie = copy.deepcopy(copiea)
                        for i2 in i1:
                            copiecopie = supprimer(copiecopie, i2)
                        # print(copiecopie)
                        listemove += [copiecopie]
                        listeajouter += [copiecopie]
            # print("si on déplace: ")
            for i in coupspossiblesbouger(a, player):
                for i1 in coupspossiblesbouger(a, player)[i]:
                    copiea = copy.deepcopy(deplacer(a, i, i1, player))
                    # print(deplacer(a, i, i1, player))
                    move += ["{" + "'move': 'move','from': [{},{},{}],'"
                                   "to': [{},{},{}]".format(i[0], i[1], i[2], i1[0], i1[1], i1[2]) + "}"]
                    listemove += [deplacer(a, i, i1, player)]
                    listebouger += [deplacer(a, i, i1, player)]
                    if uncarre(copiea, [i1[0], i1[1], i1[2]], player)[0] == True:
                        # print(removable(copiea, 1))
                        for i2 in combinaisons(removable(copiea, player)):
                            move += ["{" + "'move': 'move','from': [{},{},{}],'"
                                           "to': [{},{},{}]".format(i[0], i[1], i[2], i1[0], i1[1], i1[2]) + \
                                     "'remove': {}".format(i2) + "}"]
                            copiecopie = copy.deepcopy(copiea)
                            for i3 in i2:
                                copiecopie = supprimer(copiecopie, i3)
                            # print(copiecopie)
                            listemove += [copiecopie]
                            listebouger += [copiecopie]
            if donnermouvement == "non":
                return listemove
            else:
                return listemove, move

        # print(coups(a, 1, "oui")[1][8])
        # print(coups(a, 1, "oui")[0][8])

        moves = coups(a, a["turn"], "oui")[1]
        liste = []
        tampon1 = []
        tampon2 = []
        tampon3 = []
        tampon4 = []


        if difficultée == 1:
            for i in coups(a, a["turn"]):
                for i1 in coups(i, 1-a["turn"]):
                    for i2 in coups(i1, a["turn"]):
                        tampon2 += [i2['reserve'][a["turn"]] - i2['reserve'][1-a["turn"]]]
                    tampon1 += tampon2
                    tampon2 = []
                liste += [tampon1]
                tampon1 = []
        else:
            for i in coups(a, a["turn"]):
                for i1 in coups(i, 1-a["turn"]):
                    for i2 in coups(i1, a["turn"]):
                        for i3 in coups(i2, 1-a["turn"]):
                            tampon3 += [i3['reserve'][a["turn"]] - i3['reserve'][1-a["turn"]]]
                        tampon2 += tampon3
                        tampon3 = []
                    tampon1 += tampon2
                    tampon2 = []
                liste += [tampon1]
                tampon1 = []

        c = 0
        resultats = []
        différentscoups = []
        while c < len(liste):
            resultats += [min(liste[c])]
            # print(str(moves[c]) + "=====================>>>>>>>>>>>>>>>>" + str(min(liste[c])))
            c += 1
        return json.dumps(eval(moves[resultats.index(max(resultats))]))


if __name__ == '__main__':
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Pylos game')
    subparsers = parser.add_subparsers(description='server client', help='Pylos game components', dest='component')
    # Create the parser for the 'server' subcommand
    server_parser = subparsers.add_parser('server', help='launch a server')
    server_parser.add_argument('--host', help='hostname (default: localhost)', default='localhost')
    server_parser.add_argument('--port', help='port to listen on (default: 5000)', default=5000)
    server_parser.add_argument('--verbose', action='store_true')
    # Create the parser for the 'client' subcommand
    client_parser = subparsers.add_parser('client', help='launch a client')
    client_parser.add_argument('name', help='name of the player')
    client_parser.add_argument('--host', help='hostname of the server (default: localhost)', default='127.0.0.1')
    client_parser.add_argument('--port', help='port of the server (default: 5000)', default=5000)
    client_parser.add_argument('--verbose', action='store_true')
    # Parse the arguments of sys.args
    args = parser.parse_args()
    if args.component == 'server':
        PylosServer(verbose=args.verbose).run()
    else:
        PylosClient(args.name, (args.host, args.port), verbose=args.verbose)
