import Pyro5.api
import datetime
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import threading
from time import sleep


class Product:


    def __init__(self, codigo, name, descricao, quantidade, preco, estoqueminimo):
        self.code = codigo
        self.name = name
        self.description = descricao
        self.quantity = quantidade
        self.price = preco
        self.min_stock = estoqueminimo
        self.movements = []

    def add_entry(self, quantidade):
        self.quantity = quantidade
        self.movements.append((datetime.datetime.now(), "ENTRADA", quantidade))

    def add_exit(self, quantidade):
        if self.quantity >= quantidade:
            self.quantity -= quantidade
            self.movements.append((datetime.datetime.now(), "SAIDA", quantidade))

    def get_stock_status(self):
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "quantity": self.quantity,
            "price": self.price,
            "min_stock": self.min_stock,
        }


class User:
    def __init__(self, nome, public_key, objetocliente):
        self.nome = nome
        self.public_key = public_key
        self.client_object = objetocliente

class Estoque:
    def __init__(self):
        self.users = {} 
        self.products = {}  
        self.clients = {} 
        
    @Pyro5.api.expose
    def register_user(self, nome, public_key, client_object):
        print(public_key)
        print("Usuarios cadastrados: ", self.users)
        print("Name:", nome)

        if nome not in self.users:
            user = User(nome, public_key, client_object)
            self.users[nome] = user
            print(self.users[nome], self.users[nome].nome, self.users, self.users[nome].public_key)
            return f"{nome} cadastrado"
        else:
            print("else")
            return f"{nome} já posssui cadastro"


    @Pyro5.api.expose
    def record_entry(self, user_nome, codigo, name, description, quantity, price, min_stock, signature):

        if user_nome in self.users:

            user = self.users[user_nome]

            if codigo in self.products:

                print("Produto adicionado")
                product = self.products[codigo]

                # Verificar a assinatura digital com a chave pública do usuário
                if self.verify_signature(signature, user.public_key, user_nome):

                    print("Assinatura digital válida.")
                    product.add_entry(quantity)

                    # Verificar se a quantidade após a entrada atingiu o estoque mínimo
                    if product.quantity <= product.min_stock:

                        self.reposicao(product)
                    else: print("Notificação: Produto com baixo estoque! ")
                    return f"Entrada de {quantity} unidades de {product.name} registrada."
                    
                else:

                    print("Assinatura digital inválida.")
                    return "Assinatura digital inválida."
            else:

                print(name, codigo)
                product = Product(codigo, name, description, quantity, price, min_stock)
                self.products[codigo] = product
                self.products[codigo].add_entry(quantity)
                return f"({codigo}) {name} adicionado"
        else:

            return "Este usuario nao existe"

    @Pyro5.api.expose
    def record_exit(self, code, user_nome, quantity, signature):

        if user_nome in self.users:

            user = self.users[user_nome]
            if code in self.products:

                product = self.products[code]


                #verificacao de assinatura ->chave publica(usuario)
                if self.verify_signature(signature, user.public_key, user_nome):

                    product.add_exit(quantity)
                    return f"alterado o registro de {product.name}, com saida de {quantity} unidades"
                else:

                    return "assinatura invalida"
            else:

                return "nao esta no estoque"
        else:

            return "nao foi possivel localizar o usuario"

    def verify_signature(self, signature, public_key, message):

        return True

        public_key_bytes = base64.b64decode(public_key)

        print('tenta verificar assinatura:', message)
        print(public_key)
        try:

            public_key.verify(

                signature,
                message.encode('utf-8'),
                padding.PSS(

                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            return True  # Assinatura válida
        
        except Exception as error:

            print(error)
            return False  # Assinatura inválida



        return True
    
    @Pyro5.api.expose
    def generate_stock_report(self, report_type):

        if report_type == 'PRODUTOS EM ESTOQUE':

            emEstoque = []
            for product in self.products.values():
                    product_info = {
                        "code": product.code,
                        "name": product.name,
                        "quantity": product.quantity
                    }
                    emEstoque.append(product_info)
            return emEstoque
        
        elif report_type == 'Fluxo de movimentação':
            current_time = datetime.datetime.now()
            time = current_time - datetime.timedelta(minutes=1)

            fluxoMov = []
            for product in self.products.values():
              
                    product_info = {
                        "code": product.code,
                        "name": product.name,
                        "movements": []
                    }

                    # Filtrar os movimentos que ocorreram até 2 minutos atrás
                    for movement_time, movement_type, movement_quantity in product.movements:
                        if movement_time >= time:
                            product_info["movements"].append({
                                "time": movement_time,
                                "type": movement_type,
                                "quantity": movement_quantity
                            })

                    fluxoMov.append(product_info)
            return fluxoMov
                
        elif report_type == 'Lista de produtos sem saída':
                current_time = datetime.datetime.now()
                two_minutes_ago = current_time - datetime.timedelta(minutes=1)

                unsold_products = []

                for product in self.products.values():
                    has_exit_movements = any(
                        movement_time >= two_minutes_ago and movement_type == "saída"
                        for movement_time, movement_type, _ in product.movements
                    )

                    if not has_exit_movements:
                        unsold_products.append({
                            "code": product.code,
                            "name": product.name
                        })

        return unsold_products
                


    def check_low_stock(self):

        for product in self.products.values():
            if product.quantity <= product.min_stock:
                self.reposicao(product)


    def check_unsold_products(self):

        recent_product_movements = self.generate_stock_report("Fluxo de movimentação")
        print(recent_product_movements)

        for product in self.products.values():
            counter = 0
            for info in product.movements:
                print(info[1])
                if info[1] == "saída":
                    counter += 1
            if counter == 0:
                self.promocao(product)

    @Pyro5.api.expose 
    def reposicao(self, product):
        print(self.users)

        for user_object in self.users.items():
            print(f"o produto {product.name} está fora de estoque e precisa de reposicao")
            aux_object = Pyro5.api.Proxy(user_object.client_object)
            aux_object.notify_replenishment(product.code)
       
    @Pyro5.api.expose
    def promocao(self, product):
        for user_object in self.users.items():
            print(f"o produto {product.name} não está sendo vendido")
            aux_object = Pyro5.api.Proxy(user_object.client_object)
            aux_object.notify_unsold_products(product.code)


    def __reduce__(self):

        return (self.__class__, (self.name, self.public_key))

def periodic_check(Estoque):
    while True:
        # Verificar o estoque baixo e notificar o gestor
        Estoque.check_low_stock()
        Estoque.check_unsold_products()
        sleep(30)


# Configurar o servidor PyRO
if __name__ == "__main__":

    daemon = Pyro5.api.Daemon()

    ns = Pyro5.api.locate_ns()

    stock_system = Estoque()
    uri = daemon.register(stock_system)

    ns.register("estoque", uri)

    print("o servidor esta pronto")

    check_stock_thread = threading.Thread(target=periodic_check, args=(stock_system, )).start()

    daemon.requestLoop()
