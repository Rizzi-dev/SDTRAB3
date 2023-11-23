import Pyro5.api
import threading
import inquirer
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
Pyro5.api.config.SERIALIZER = 'marshal'


# Gestão do Estoque
class Estoque:

    @Pyro5.api.expose 
    def notify_replenishment(self, product_code):
        print(f"> Notificação: Produto de código {product_code} está abaixo do estoque mínimo. É necessário repor o estoque.")

    @Pyro5.api.expose 
    def notify_unsold_products(self, product):
        print(f"> Notificação: {product['name']} ({product['code']}) não foi vendido.")


def keysGenerator():
    private_key = rsa.generate_private_key(
        public_exponent=65537,  
        key_size=2048,         
        backend=default_backend()
    )

    # Obter a chave pública correspondente
    public_key = private_key.public_key()

    # Serializar as chaves para armazenamento ou transmissão
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Salvar as chaves em arquivos
    with open("private_key.pem", "wb") as f:
        f.write(private_key_pem)

    with open("public_key.pem", "wb") as f:
        f.write(public_key_pem)

    print("CHAVES GERADAS AUTOMATICAMENTE! AS CHAVES FORAM GRAVADAS NA PASTA RAIZ")
    return [private_key_pem, public_key_pem, private_key]


# Função para assinar uma mensagem com a chave privada
def sign_message(message, private_key):
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature




daemon = Pyro5.api.Daemon()
uri = daemon.register(Estoque())
keys = keysGenerator()
private_key = keys[0]
public_key = keys[1]
pk = keys[2]
servidor_nomes = Pyro5.api.locate_ns()
server_uri = servidor_nomes.lookup("estoque")
server = Pyro5.api.Proxy(server_uri) 

print("----- SEJA BEM VINDO AO SISTEMA DE ESTOQUE! -----")
print("-----           LOGIN DE USUÁRIO:           -----")
nome = input("NOME: ")
response = server.register_user(nome, public_key, uri)
print(response)
threading.Thread(target=daemon.requestLoop).start()
message = nome
signature = sign_message(message, pk)
#Menu de opções
while(True):
    questions = [
            inquirer.List('action', message="MENU", 
                        choices=['Entrada de produtos', 'Saida de produtos', 'Relatorio'],)
    ]
    answer = inquirer.prompt(questions)
    print(answer)
    if(answer['action'] == 'Entrada de produtos'):
            
            codstr = input("Codigo do produto: ")
            codigo = int(codstr)
            name = input("Produto que deseja adicionar: ")
            description = input("Descrição: ")
            quantidadestr = input("Quantidade: ")
            quantity = int(quantidadestr)
            price = input("Qual o preço deste produto? : ")
            server.record_entry(nome, codigo, name, description, quantity, price, 10, signature)
            print("PRODUTO REGISTRADO COM SUCESSO")
    elif(answer['action'] == 'Saida de produtos'):
            print('Saida de produtos')
            codsaidastr = input("Informe o codigo do produto: ")
            codsaida = int(codsaidastr)
            qntsaidastr = input("Informe a quantidade que deseja retirar: ")
            qntsaida = int(qntsaidastr)
            server.record_exit(codsaida, nome, qntsaida, signature)
            print("SAÍDA EFETUADA COM SUCESSO PARA O PRODUTO:   " +name)
    elif(answer['action'] == 'Relatorio'):
            print('Relatorio')
            questions2 = [
            inquirer.List('action2', message="Escolha um relatório para gerar: ", 
                        choices=['Produtos em estoque', 'Fluxo de movimentação', 'Lista de produtos sem saída'])
            ]
            answer = inquirer.prompt(questions2)
            if(answer['action2']== 'Produtos em estoque'):
                print('Produtos em estoque')
                produtosEmEstoque= server.generate_stock_report('Produtos em estoque')
                for product in produtosEmEstoque:
                    print(f"Produto {product['name']} - ({product['code']}) {product['quantity']} unidades em estoque")
            elif(answer['action2']== 'Fluxo de movimentação'):
                    print('Fluxo de movimentação')
                    fluxoMov= server.generate_stock_report('Fluxo de movimentação')
                    print("Movimentos:")
                    for product in fluxoMov:
                        for movement in product['movements']:
                            print(f"Produto {product['name']} ({product['code']})  - Tipo: {movement['type']}, Quantidade: {movement['quantity']}, Hora: {movement['time']}")
            elif(answer['action2']== 'Lista de produtos sem saída'):
                    print('Lista de produtos sem saída')
                    prodSemSaida = server.generate_stock_report('Lista de produtos sem saída')
                    for product in prodSemSaida :
                        print(f"Produto {product['name']} ({product['code']}) não teve movimentos de saída até 2 minutos atrás.")
