#!/usr/bin/env python3
# pylos.py
# Author: Quentin Lurkin
# Version: April 28, 2017
# -*- coding: utf-8 -*-

import argparse
import socket
import sys
import json
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
                    matrix.append([None]*size)
                return matrix

            board = []
            for i in range(4):
                board.append(squareMatrix(4-i))

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
            #return None si vide, 1 ou 0 en fonction du joueur
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
                self.get(layer-1, row, column) == None or
                self.get(layer-1, row+1, column) == None or
                self.get(layer-1, row+1, column+1) == None or
                self.get(layer-1, row, column+1) == None
            ):
                raise game.InvalidMoveException('The position ({}) is not stable'.format([layer, row, column]))

    def canMove(self, layer, row, column):
        '''Verifie si la place est vide, et s'il y a une piéce au dessus'''
        if self.get(layer, row, column) == None:
            raise game.InvalidMoveException('The position ({}) is empty'.format([layer, row, column]))

        if layer < 3:
            if (
                self.safeGet(layer+1, row, column) != None or
                self.safeGet(layer+1, row-1, column) != None or
                self.safeGet(layer+1, row-1, column-1) != None or
                self.safeGet(layer+1, row, column-1) != None
            ):
                raise game.InvalidMoveException('The position ({}) is not movable'.format([layer, row, column]))

    def createSquare(self, coord):
        '''Regarde si on a créé une carré'''
        layer, row, column = tuple(coord)

        def isSquare(layer, row, column):
            if (
                self.safeGet(layer, row, column) != None and
                self.safeGet(layer, row+1, column) == self.safeGet(layer, row, column) and
                self.safeGet(layer, row+1, column+1) == self.safeGet(layer, row, column) and
                self.safeGet(layer, row, column+1) == self.safeGet(layer, row, column)
            ):
                return True
            return False

        if (
            isSquare(layer, row, column) or
            isSquare(layer, row-1, column) or
            isSquare(layer, row-1, column-1) or
            isSquare(layer, row, column-1)
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
        print(' ' + '_'*(len(matrix)*2-1))
        print('\n'.join(map(lambda row : '|' + '|'.join(map(self.val2str, row)) + '|', matrix)))

    # print the state
    def prettyprint(self):
        state = self._state['visible']
        for layer in range(4):
            self.printSquare(state['board'][layer])
            print()
        
        for player, reserve in enumerate(state['reserve']):
            print('Reserve of {}:'.format(self.player2str(player)))
            print((self.val2str(player)+' ')*reserve)
            print()
        
        print('{} to play !'.format(self.player2str(state['turn'])))
        #print(json.dumps(self._state['visible'], indent=4))       

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
        self.__dontmove = []
        super().__init__(server, PylosState, verbose=verbose)
        self.__name = name

    def _handle(self, message):
        pass
    
    #return move as string
    def _nextmove(self, state):
        '''
        example of moves
        coordinates are like [layer, row, colums]
        move = {
            'move': 'place',
            'to': [0,1,1]
        }

        move = {
            'move': 'move',
            'from': [0,1,1],
            'to': [1,1,1]
        }

        move = {
            'move': 'move',
            'from': [0,1,1],
            'to': [1,1,1]
            'remove': [
                [1,1,1],
                [1,1,2]
            ]
        }

        return it in JSON
        '''

        iterration = 3
        t = Tree(state, 0, iterration)
        #print(t)

        if state._state['visible']['turn'] == 0:
            player = 0
            notplayer = 1
        else:
            player = 1
            notplayer = 0

        print("I'm:", player)

        delta_save = 0
        bestmove = {}
        coup = {}

        for gen1 in t:
            if gen1.state._state['visible']['reserve'][notplayer] == 1 or gen1.state._state['visible']['reserve'][player] == 1:
                coup['move'] = gen1.coup['move']
                coup['to'] = list(gen1.coup['to'])
                return json.dumps(coup)

            for gen2 in gen1:
                coup_2 = gen2.coup['to']

                if state._state['visible']['board'][coup_2[0]][coup_2[1]][coup_2[2]] is None:
                    if gen2.state.createSquare(coup_2):
                        print("Je bloque le carré")
                        self.__dontmove.append(coup_2)
                        return json.dumps({'move': 'place',
                                           'to': list(coup_2)})

                for gen3 in gen2:
                    if player == 0:
                        delta_reserve = 0
                        delta_reserve += gen1.state._state['visible']['reserve'][notplayer] - gen1.state._state['visible']['reserve'][player]
                        delta_reserve += gen2.state._state['visible']['reserve'][notplayer] - gen2.state._state['visible']['reserve'][player]
                        delta_reserve += gen3.state._state['visible']['reserve'][notplayer] - gen3.state._state['visible']['reserve'][player]
                    else:
                        delta_reserve = 0
                        delta_reserve += gen1.state._state['visible']['reserve'][player] - gen1.state._state['visible']['reserve'][notplayer]
                        delta_reserve += gen2.state._state['visible']['reserve'][player] - gen2.state._state['visible']['reserve'][notplayer]
                        delta_reserve += gen3.state._state['visible']['reserve'][player] - gen3.state._state['visible']['reserve'][notplayer]


                    if len(self.__dontmove) > 0 and gen1.coup['move'] == 'move':
                            if gen1.coup['from'] in self.__dontmove:
                                pass
                            else:
                                if delta_reserve > delta_save:
                                    delta_save = delta_reserve
                                    bestmove = gen1.coup

                    else:
                        if delta_reserve > delta_save:
                            delta_save = delta_reserve
                            bestmove = gen1.coup


        if bestmove['move'] == 'place':
            coup['move'] = bestmove['move']
            coup['to'] = list(bestmove['to'])

            return json.dumps(coup)

        elif bestmove['move'] == 'move':
            coup['move'] = bestmove['move']
            coup['from'] = list(bestmove['from'])
            coup['to'] = list(bestmove['to'])

            return json.dumps(coup)



#        for layer in range(4):
#            for row in range(4-layer):
#                for column in range(4-layer):
#                    if state.get(layer, row, column) == None:
#                        return json.dumps({
#                            'move': 'place',
#                            'to': [layer, row, column]
#                        })

class Tree:
    def __init__(self, state, tour, iterration, coup={}, children=[]):
        self.__state = copy.deepcopy(state)
        self.__player = self.__state._state['visible']['turn']
        self.__iterration = iterration
        self.__coup = coup #Permet de savoir si on place ou si on bouge et où

        self.__children = copy.deepcopy(children)
        self.__tour = tour

        self._coupvalide(self.__state)

    def __str__(self):
        '''Affiche l'arbre et ses enfants'''
        def _str(tree, level):
            result = '{} [from:{} to:{}]\n{}{}\n'.format(tree.coup['move'],
                                                         tree.coup['from'],
                                                         tree.coup['to'],
                                                         '    ' * level,
                                                         tree.state._state['visible'])
            for child in tree.children:
                result += '{}|--{}'.format('    ' * level, _str(child, level + 1))
            return result
        return _str(self, 0)

    def __getitem__(self, item):
        '''Permet de faire des boucle for dans l'arbre'''
        return self.__children[item]

    @property
    def state(self):
        return self.__state

    @property
    def children(self):
        return self.__children

    @property
    def coup(self):
        coup = {}
        if len(self.__coup) == 0:
            coup['move'] = ''
            coup['to'] = ''
            coup['from'] = ''
            return coup
        else:
            return self.__coup

    def _possibleplacement(self, state):
        '''Enregistre toute les places où on peut faire un placement'''
        possibleplacement = []
        for move in self._getplace(state):
            try:
                state.validPosition(move[0], move[1], move[2])
                possibleplacement.append(move)
            except:
                pass

        return possibleplacement

    def _getplace(self, state):
        '''Cherche toute les places vide sur le plateau'''
        statue = state._state['visible']['board']
        move = []
        layer = 0

        while layer <= 3:
            number_line = 0
            indice = 0
            long_layer = len(statue[layer])

            while number_line < long_layer:
                lines = statue[layer][number_line]

                for place in lines:
                    if place is None:
                        move.append((layer, indice//long_layer, indice%long_layer))
                    indice += 1

                number_line += 1
            layer += 1
        return move

    def _possiblemove(self, state):
        '''Enregistre toute les places des billes qu'on peut déplacer'''
        possiblemove = []
        for move in self._getmove(state):
            try:
                state.canMove(move[0], move[1], move[2])
                possiblemove.append(move)
            except:
                pass

        return possiblemove

    def _getmove(self, state):
        '''Cherche toute les places des billes qui sont à nous'''
        move = []
        statue = state._state['visible']['board']
        player = state._state['visible']['turn']
        layer = 0

        while layer < 3:
            long_layer = len(statue[layer])
            indice = 0
            number_line = 0

            while number_line < long_layer:
                lines = statue[layer][number_line]

                for place in lines:
                    if place is not None and place == player:
                        move.append((layer, indice // long_layer, indice % long_layer))
                    indice += 1

                number_line += 1
            layer += 1

        return move

    def _coupvalide(self, state):
        possibleplacement = self._possibleplacement(state)
        possiblemove = self._possiblemove(state)

        #Pour chaque PLACEMENT possible on créé des enfants
        for move in possibleplacement:
            new_state = copy.deepcopy(state)
            new_state._state['visible']['board'][move[0]][move[1]][move[2]] = self.__player
            new_state._state['visible']['reserve'][self.__player] -= 1

            #limitation des ittérations
            if self.__iterration > 0:
                if self.__player == 0:
                    #Permetra de savoir le mouvement et la coord
                    movement = {}
                    movement['move'] = 'place'
                    movement['to'] = move
                    movement['from'] = ''

                    iterration = self.__iterration - 1
                    new_state._state['visible']['turn'] = 1
                    tour = self.__tour + 1
                    self.__children.append(Tree(new_state, tour, iterration, movement))
                else:
                    # Permetra de savoir le mouvement et la coord
                    movement = {}
                    movement['move'] = 'place'
                    movement['to'] = move
                    movement['from'] = ''

                    iterration = self.__iterration - 1
                    new_state._state['visible']['turn'] = 0
                    tour = self.__tour + 1
                    self.__children.append(Tree(new_state, tour, iterration, movement))

        #Pour chaque MOUVEMENT possible on crée des enfants
        #(prendre une boulle du plateau et la poser au layer suivant)
        for move in possiblemove: #Prend chaque boulle qu'on peut bouger
            for place in possibleplacement: #Prend chaque postion libre
                new_state = copy.deepcopy(state)

                if place[0] > move[0]:
                    try:
                        #Enleve la boulle, verifie la position final et place la boule
                        new_state._state['visible']['board'][move[0]][move[1]][move[2]] = None
                        new_state.validPosition(place[0], place[1], place[2])
                        new_state._state['visible']['board'][place[0]][place[1]][place[2]] = self.__player

                        # limitation des ittérations
                        if self.__iterration > 0:
                            if self.__player == 0:
                                # Permetra de savoir le mouvement et les coords
                                mouvement = {}
                                movement['move'] = 'move'
                                movement['to'] = place
                                movement['from'] = move

                                iterration = self.__iterration - 1
                                new_state._state['visible']['turn'] = 1
                                tour = self.__tour + 1
                                self.__children.append(Tree(new_state, tour, iterration, movement))
                            else:
                                # Permetra de savoir le mouvement et les coords
                                movement = {}
                                movement['move'] = 'move'
                                movement['to'] = place
                                movement['from'] = move

                                iterration = self.__iterration - 1
                                new_state._state['visible']['turn'] = 0
                                tour = self.__tour + 1
                                self.__children.append(Tree(new_state, tour, iterration, movement))
                    except:
                        pass

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